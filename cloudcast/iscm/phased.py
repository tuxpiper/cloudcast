from cloudcast.iscm import ISCM
from cloudcast.iscm.cfninit import CfnInit, CfnInitISCM

from cloudcast.template import *

def _dict_to_stable_str(dic):
    # Get a stable representation of a nested data structure into string
    from pprint import pformat
    return pformat(dic, width=2**16)

PURPOSE_BUILD = "build"
PURPOSE_RUN = "run"

class PhasedISCM(ISCM):
    def __init__(self, context=None, phases=None, **kwargs):
        self.phases = phases
        self.phase_names = [ p.phase_name for p in phases ]
        self.cfn_init = CfnInitISCM(context["_iscm"]["cfninit_key"])
        #
        ISCM.__init__(self, context, [self.cfn_init], phases, **kwargs)
        #

    def is_buildable(self):
        return True

    def set_phases_to_run(self, phases):
        configsets = []
        for p in phases: configsets.append(p.phase_name)
        self.iscm_cfninit_run_configsets(*configsets)
        
    def get_possible_builds(self, purpose=PURPOSE_RUN):
        """
        Returns a list of possible status ids that are valid entry points
        into this ISCM. For each status, there is a list of phases that need
        to be executed, i.e.:

        [
         { status_id: "ykyk...", run_phases: [ ] },
         { status_id: "znzn...", run_phases: [ <phase3> ] },
         { status_id: "xyxy...", run_phases: [ <phase2>, <phase3> ] },
         { status_id: "",        run_phases: [ <phase1>, <phase2>, <phase3> ] },
        ]

        the array is sorted in such a way that entries with the least pending
        phases are found first.

        When purpose = PURPOSE_BUILD, each runnable path contains a list of the
        buildable targets and the phases that need to be run to achieve them:

        [
         { status_id: "ykyk...", targets = [] },
         { status_id: "znzn...", targets=[
          { target_id: "ykyk...", run_phases: [ <phase3> ] },
         ]},
         { status_id: "xyxy...", targets=[
          { target_id: "ykyk...", run_phases: [ <phase2>, <phase3> ] },
          { target_id: "znzn...", run_phases: [ <phase2> ] },
         ]},
         { status_id: "", targets=[
          { target_id: "ykyk...", run_phases: [ <phase1>, <phase2>, <phase3> ] },
          { target_id: "znzn...", run_phases: [ <phase1>, <phase2> ] },
          { target_id: "xyxy...", run_phases: [ <phase1> ] },
         ]}
        ]
        """
        import hashlib
        from copy import copy
        
        phases = self.phases
        pending_list = copy(phases)
        must_run_list = []
        stages = [ dict(status_id="", must_run=copy(must_run_list), pending=copy(pending_list)) ]
        hashsum = hashlib.sha256()
        status_id_after = {}    # after phase_name
        #
        for p in copy(pending_list):
            hashsum.update(_dict_to_stable_str(p.get_dict_repr()))
            status_id_after[p.phase_name] = hashsum.hexdigest()
            pending_list = pending_list[1:]
            if p.phase_type == RUN_EVERY_TIME:
                must_run_list.append(p)
                continue
            elif p.phase_type == RUN_ON_UPDATE and purpose == PURPOSE_BUILD:
                must_run_list.append(p)
                continue
            elif p.phase_type == RUN_ONCE:
                # possible point of entry for AMIs
                stages.insert(0, dict(status_id=hashsum.hexdigest(), must_run=copy(must_run_list), pending=copy(pending_list)))
            elif p.phase_type == RUN_ON_DEPLOY:
                # no more saved entry points possible
                break
        #
        # If we are building images, add possible builds from each entry point
        if purpose == PURPOSE_BUILD:
            for rp in stages:
                targets = []
                must_run = rp["must_run"]
                pending = rp["pending"]
                del rp["must_run"]
                del rp["pending"]
                iterated = []
                for p in pending:
                    iterated.append(p)
                    if p.phase_type == RUN_ONCE:
                        # this makes a new target
                        target = dict(target_id=status_id_after[p.phase_name], run_phases=must_run + iterated)
                        targets.insert(0, target)
                rp["targets"] = targets
        else:
            for rp in stages:
                rp["run_phases"] = rp["must_run"] + rp["pending"]
                del rp["must_run"]
                del rp["pending"]
        #
        return stages

# definitions of phase types
RUN_ON_UPDATE = "run_on_update"
RUN_EVERY_TIME = "run_every_time"
RUN_ONCE = "run_once"
RUN_ON_DEPLOY = "run_on_deploy"

from contextlib import contextmanager
class Phase(object):    
    def __init__(self, phase_name, phase_type, modules):
        self.phase_name = phase_name
        self.phase_type = phase_type
        self.cfn_configs = []
        self.modules = modules
        self.actions = dict(
            dict_updates = {},
            cfninit_configs = {}
        )

    def get_dict_repr(self):
        """
        Return a dictionary representation of this phase.
        This will be used for checksumming, in order to uniquely compare
        instance images against their requirements
        """
        return dict(
            phase_name = self.phase_name,
            phase_type = self.phase_type,
            actions = self.actions
            )

    def install(self, iscm):
        for mod in self.modules:
            mod.install(iscm)

    def deploy(self, iscm):
        with self._hijacked_iscm_calls(iscm):
            for mod in self.modules:
                mod.deploy(iscm)

    def __repr__(self):
        return "<%s('%s')>" % (self.__class__.__name__, self.phase_name)

    @contextmanager
    def _hijacked_iscm_calls(self, iscm):
        # We intercept a couple of iscm calls, so we can obtain the actions
        # that the submodules create. We use that for checksumming and
        # managing the actions of each phase

        #
        # Copy references to old methods
        iscm._hijacked = {
            "iscm_md_update_dict": iscm.iscm_md_update_dict,
            "iscm_cfninit_add_config": iscm.iscm_cfninit_add_config
        }
        # Define hijackers
        phase = self
        def iscm_md_update_dict(self, keypath, data):
            # This is used for variable setting mostly...
            if not phase.actions['dict_updates'].has_key(keypath):
                phase.actions['dict_updates'][keypath] = []
            phase.actions['dict_updates'][keypath].append(data)
            # Invoke hijacked method
            return self._hijacked["iscm_md_update_dict"](keypath, data)
        def iscm_cfninit_add_config(self, config, name=None):
            # This is used for adding deployable files/code
            if name is None:
                name = "%s-%03d" % (phase.phase_name, len(phase.actions['cfninit_configs']) + 1)
            phase.actions['cfninit_configs'][name] = config
            phase.cfn_configs.append(name)
            # Invoke hijacked method
            return self._hijacked["iscm_cfninit_add_config"](config, name)
        # Set hijackers in iscm instance
        import types
        iscm.iscm_md_update_dict = types.MethodType(iscm_md_update_dict, iscm)
        iscm.iscm_cfninit_add_config = types.MethodType(iscm_cfninit_add_config, iscm)
        # yield control
        yield
        # Create config set for the phase, once all configs have been added
        iscm.iscm_cfninit_add_configset(self.phase_name, *self.cfn_configs)
        # Restore methods
        iscm.iscm_md_update_dict = iscm._hijacked["iscm_md_update_dict"]
        iscm.iscm_cfninit_add_config = iscm._hijacked["iscm_cfninit_add_config"]


class RunOnUpdate(Phase):
    def __init__(self, phase_name, modules):
        Phase.__init__(self, phase_name, RUN_ON_UPDATE, modules)

class RunAlways(Phase):
    def __init__(self, phase_name, modules):
        Phase.__init__(self, phase_name, RUN_EVERY_TIME, modules)

class RunOnce(Phase):
    def __init__(self, phase_name, modules):
        Phase.__init__(self, phase_name, RUN_ONCE, modules)

class RunOnDeploy(Phase):
    def __init__(self, phase_name, modules):
        Phase.__init__(self, phase_name, RUN_ON_DEPLOY, modules)
