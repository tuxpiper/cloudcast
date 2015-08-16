from cloudcast.iscm.cfninit import CfnEmbedFile
from cloudcast.iscm.phased import PhasedISCM, RunAlways, RunOnce, RunOnDeploy
from cloudcast._utils import caller_folder, search_path
from cloudcast.template import AWS, Resource

from copy import copy
from os import getcwd
import os

_ansibleinstall_script = os.path.join(os.path.dirname(__file__), "scripts", "install_ansible.sh")

"""
Wrapper for the standard pattern of having ansible initialization and boot module.

Some examples:


"""
class AnsibleISCM(PhasedISCM):
  def __init__(self, **kwargs):
    # valid kwargs
    #  * config
    #  * stack_user_key
    #  * facts
    #  * vars
    #  * playbooks_source / (playbook_sources)
    #  * boot / (runs)
    if not kwargs.has_key("stack_user_key"):
      raise RuntimeError("Required AnsibleISCM argument 'stack_user_key' missing!")

    # The context of the ISCM is defined from the facts and the stack_user_key
    if kwargs.has_key('facts'):
      context = copy(kwargs['facts'])
    else:
      context = {}
    context["_iscm"] = { "cfninit_key": kwargs["stack_user_key"] }

    # Prepare config ISCM module
    cfg_kwargs = dict( filter(lambda (k,v): k in AnsibleConfig.init_kwargs, kwargs.items()) )
    cfg_kwargs['_basepath'] = caller_folder()
    cfg_module = AnsibleConfig(**cfg_kwargs)

    # Standard set of build phases: config, build, boot
    phases = [ RunAlways( "AnsibleConfig", [ cfg_module ] ) ]
    if cfg_module.run_manager.has_run('build'):
      phases.append(RunOnce("Ansible-Build", [ Ansible('build') ]))
    if cfg_module.run_manager.has_run('boot'):
      phases.append(RunOnDeploy("Ansible-Boot", [ Ansible('boot') ]))

    # Initialize the phased ISCM that we wrap around
    PhasedISCM.__init__(self, context, phases)

"""
ISCM module to configure ansible install in the instance
"""
class AnsibleConfig(object):
  init_kwargs = [ "config", "facts", "playbooks_source", "boot", "runs", "_basepath" ]
  def __init__(self, **kwargs):
    # Get the basepath from which playbook files can be searched locally
    if kwargs.has_key('_basepath'):
      self.basepath = kwargs['_basepath']
    else:
      self.basepath = caller_folder()
    #
    self.config = {}
    if kwargs.has_key("config"): self.config = kwargs["config"]
    self._check_config()
    #
    self.pb_sources = _AnsiblePlaybookSources(config=self.config, basepath=self.basepath)
    if kwargs.has_key('playbooks_source'):
      self.pb_sources.add_folder(kwargs['playbooks_source'])
    #
    self.facts = {}
    if kwargs.has_key("facts"): self.facts = kwargs["facts"]
    #
    if kwargs.has_key("boot"):
      self.run_manager = _AnsibleRunManager(boot=kwargs["boot"], ansible_config=self.config)
    else:
      self.run_manager = _AnsibleRunManager(runs=kwargs["runs"], ansible_config=self.config)

  def _check_config(self):
    for k in self.config.keys():
      if k not in [ 'ansible_home', 'ansible_version', 'sudo', 'tags', 'skip_tags', 'inst_home', 'inst_playbook_dir', 'inst_user', 'inst_group' ]:
        raise RuntimeError("Unknown AnsibleConfig directive %s" % k)
    #
    if not self.config.has_key('inst_home') or \
       not self.config.has_key('inst_user') or \
       not self.config.has_key('inst_group') or \
       not self.config.has_key('inst_playbook_dir'):
      raise RuntimeError("Missing required configuration for AnsibleConfig")
    #
    if not self.config.has_key('ansible_version'):
      self.config['ansible_version'] = "1.8.2"
    #
    if not self.config.has_key('ansible_home'):
      self.config['ansible_home'] = "/opt/cfn-ansible"
    #
    from os.path import isabs, join
    inst_pb_dest_path = self.config['inst_playbook_dir']
    if not isabs(inst_pb_dest_path):
      inst_pb_dest_path = join(self.config['inst_home'], inst_pb_dest_path)
    if not isabs(inst_pb_dest_path):
      raise RuntimeError("Can't interpolate absolute path in the instance for playbooks to be!")
    self.config['_inst_playbook_path'] = inst_pb_dest_path

  def _get_ansible_install_inventory(self, iscm):
    ans_home = self.config['ansible_home']
    return dict(
      files= {
          "%s/etc/hosts" % ans_home : dict(
            content= \
             "[local]\n" + \
             "localhost\n\n" + \
             "[targets]\n" + \
             "localhost\tansible_connection=local ansible_python_interpreter=%s/bin/python\n" % ans_home,
            owner= 'root',
            group= 'root',
            mode= "000644"
            )
        })

  def _get_ansible_install_facts_cfninit(self, iscm):
    stack_user_key = iscm.iscm_cfninit_get_stack_user_key()
    ans_home = self.config['ansible_home']
    return dict(
      commands= dict(
        ansible_get_facts= dict(
          command= {
           "Fn::Join" : ["", [
            '[ ! -d %s/etc/host_vars ] && mkdir -p %s/etc/host_vars ; ' % (ans_home, ans_home),
            'cfn-get-metadata --access-key ', stack_user_key,
            ' --secret-key ', stack_user_key["SecretAccessKey"],
            ' --region ', AWS.Region,
            ' --stack ', AWS.StackName,
            ' --resource ', Resource.ThisName(),
            ' --k _ansible_facts ',
#            " | ( . %s/bin/activate ; python -c 'import json, yaml, sys ; print yaml.safe_dump(json.load(sys.stdin), default_flow_style=False, explicit_start=True, indent=2, allow_unicode=True)' ; ) " % ans_home,
            ' > %s/etc/host_vars/localhost.json' % ans_home
            ] ]
          }
        )
      )
    )
    
  def install(self, iscm):
    # This iscm module uses the cfn-init module to deploy and execute
    # its payload. If it's not installed we shall fail
    if not hasattr(iscm, "iscm_cfninit_add_config"):
      raise RuntimeError("The Shell ISCM module depends on the CfnInit module to be installed in the same chain")
    # There can only be one of us
    if iscm.iscm_get_flag("ansible_is_configured"):
      raise RuntimeError("Only one AnsibleConfig module allowed per ISCM object")
    iscm.iscm_set_flag("ansible_is_configured")
    # Save some variables that are useful to other modules
    iscm.iscm_set_var("ansible_inst_user", self.config['inst_user'])
    iscm.iscm_set_var("ansible_run_script", os.path.join(self.config['inst_home'], 'cfn-ansible.sh'))
    # Install references to the runs in the iscm
    self.run_manager.install(iscm)

  def deploy(self, iscm):
    stack_user_key = iscm.iscm_cfninit_get_stack_user_key()
    # Place the context variables (facts) into a section of the metadata
    facts_md_entry = "_ansible_facts"
    # Add aws config to facts
    self.facts.update({
      'aws_access_key': stack_user_key,
      'aws_secret_key': stack_user_key["SecretAccessKey"],
      'aws_region': AWS.Region
    })
    iscm.iscm_md_update_dict(facts_md_entry, self.facts)
    # Make sure ansible is installed
    CfnEmbedFile(src_file=_ansibleinstall_script, dest_path="/root/install-ansible.sh", owner="root", group="root", mode="000700").deploy(iscm)
    iscm.iscm_cfninit_add_config({
        "commands": {
          "ansible_install": {
            "command": "/root/install-ansible.sh",
            "env": {
              "ANSIBLE_HOME": self.config['ansible_home'],
              "ANSIBLE_VERSION": self.config['ansible_version']
              }
            }
          }
        },
        "_ansible_install")
    # Add inventory file
    iscm.iscm_cfninit_add_config(self._get_ansible_install_inventory(iscm), "_ansible_install_inventory")
    # Install facts
    iscm.iscm_cfninit_add_config(self._get_ansible_install_facts_cfninit(iscm), "_ansible_install_facts")
    # Embed the playbook sources
    self.pb_sources.deploy(iscm)
    # Deploy the script that wraps the ansible runs as specified
    self.run_manager.deploy(iscm)

"""
This class handles the playbook sources to be installed into the instance
"""
from fs.multifs import MultiFS
from fs.osfs import OSFS
class _AnsiblePlaybookSources(object):
  def __init__(self, **kwargs):
    self.fs = MultiFS()
    self.config = kwargs['config']
    self.basepath = kwargs['basepath']

  def add_folder(self, folder_path, dest=""):
    real_path = search_path(folder_path, self.basepath, getcwd())
    if real_path is None:
      raise RuntimeError("Couldn't find ansible playbook sources at %s" % folder_path)
    self.fs.addfs(dest, OSFS(real_path))

  # TODO: In the future...
  # def add_git(self, **kwargs):
  # def add_file_url(self, url):

  # Plain method to embed the playbook contents into the cloudformation template
  def _fs_to_cfninit_plain(self):
    from base64 import b64encode
    # Create a metadata object that, when executed by cfn-init, will result in the files
    # being created in the instance
    from os.path import join
    files_obj = {}
    target = self.config['_inst_playbook_path']
    for (fs_dir, fs_dirfiles) in self.fs.walk():
      # TODO: more deterministic order of walking through the files
      if fs_dir[0] == '/': fs_dir = fs_dir[1:]
      t = join(target, fs_dir)
      for f in fs_dirfiles:
        src = join(fs_dir, f)
        dest = join(t, f)
        encoding= None
        try:
          contents= self.fs.getcontents(src, mode='rb')
          contents.decode('utf-8')
        except UnicodeDecodeError:
          encoding= "base64"
          contents= b64encode(contents)

        files_obj[dest] = dict(
          content= contents,
          owner= self.config['inst_user'],
          group= self.config['inst_group'],
          mode= "000640"
          )
        files_obj[dest].update( {"encoding": encoding} if encoding else {} )
    return files_obj

  def deploy(self, iscm):
    # Create cfn-init stanzas for creating the added files
    iscm.iscm_cfninit_add_config({ "files": self._fs_to_cfninit_plain() }, "_ansible_playbooks_install")

"""
Specification of an ansible run.

  {
    "playbook": "ansible/foo.yml"
    "extra_vars": { ... },
    "sudo": True,
    "sudo_user": "xxx",
    "tags": [ "tag1", "tag2" ],
    "skip_tags": [ "tag3", "tag4" ]
  }

"""
class _AnsibleRun(object):
  def __init__(self, run_spec, name=None):
    self.name = name
    if type(run_spec) == str:
      run_spec = yaml_load(run_spec)
    self.run_spec = run_spec
    try:
      self._check_spec()
    except Exception as e:
      raise RuntimeError("When creating ansible run '%s': '%s'" % (name, e.message))

  def _check_spec(self):
    valid_keys = [ "playbook", "extra_vars", "sudo", "sudo_user", "tags", "skip_tags" ]
    for k in self.run_spec.keys():
      if k not in valid_keys:
        raise RuntimeError("Unknown Run directive %s" % k)
    #
    if type(self.run_spec['playbook']) != str:
      raise RuntimeError("Invalid type for playbook property")

  def _exec_sh(self):
    from json import dumps as json_dumps
    command = "ansible-playbook " + \
      "-i ${ANSIBLE_INVENTORY} "

    if self.run_spec.has_key('sudo') and self.run_spec['sudo']:
      command += "-s "
    if self.run_spec.has_key('sudo_user'):
      command += "-U " % self.run_spec['sudo_user']
    if self.run_spec.has_key('extra_vars'):
      command += "-e '" + json_dumps(self.run_spec['extra_vars']) + "' "
    if self.run_spec.has_key('tags'):
      command += "-t '" + ','.join(self.run_spec['tags']) + "' "
    if self.run_spec.has_key('skip_tags'):
      command += "--skip-tags='" + ','.join(self.run_spec['skip_tags']) + "' "

    command += self.run_spec['playbook']

    return command

"""
Initializes and manages the deployment of the different ansible runs
"""
class _AnsibleRunManager(object):
  def __init__(self, boot=None, runs=None, ansible_config={}):
    if boot is not None:
      self.runs = { "boot": _AnsibleRun(boot) }
    else:
      self.runs = dict( map( lambda(k,v): (k, _AnsibleRun(v,k)), runs.items()) )
    self.ansible_config = ansible_config

  def has_run(self, name):
    return name in self.runs.keys()

  def _get_runner_clause(self, name):
    run = self.runs[name]
    return \
      " %s)\n" % name + \
      " " + run._exec_sh() + \
      "  ;;"

  def install(self, iscm):
    iscm.iscm_set_var("ansible_runs", self.runs.keys())

  def deploy(self, iscm):
    ansi_home = self.ansible_config['ansible_home']
    inst_home = self.ansible_config['inst_home']
    ansi_script = iscm.iscm_get_var("ansible_run_script")
    pb_home = self.ansible_config['_inst_playbook_path']
    files = {
      ansi_script : dict(
        content= \
          "#!/bin/bash\n\n" + \
          ". %s/bin/activate\n\n" % ansi_home + \
          "ANSIBLE_INVENTORY=%s/etc/hosts\n" % ansi_home + \
          "cd %s\n" % pb_home + \
          "case \"$1\" in \n" + \
          reduce(lambda x,y: x + self._get_runner_clause(y), self.runs.keys(), "") + \
          " *)\n" + \
          "  echo \"Invalid ansible run name $1\" && exit 1\n" + \
          "  ;;\n" + \
          "esac\n",
        owner= self.ansible_config['inst_user'],
        group= self.ansible_config['inst_group'],
        mode= "000700"
        )
      }
    iscm.iscm_cfninit_add_config({ "files": files }, "_ansible_playbooks_runner")

"""
ISCM module to embed playbook execution into an ISCM
"""
class Ansible(object):
  def __init__(self, run_name, vars=None): 
    self.run_name = run_name

  def install(self, iscm):
    # We require an ansible configuration installed previously on the ISCM
    if not iscm.iscm_get_flag("ansible_is_configured"):
      raise RuntimeError("AnsibleConfig module required in order to execute an ansible script")
    # Check that the run exists in the iscm
    if not self.run_name in iscm.iscm_get_var('ansible_runs'):
      raise RuntimeError("Ansible run '%s' is not configured in the ISCM" % self.run_name)

  def deploy(self, iscm):
    # Create execution clause for the playbook
    ansi_user = iscm.iscm_get_var("ansible_inst_user")
    ansi_script = iscm.iscm_get_var("ansible_run_script")
    iscm.iscm_cfninit_add_config({
      "commands": {
        "ansible-run": dict(
          command="sudo -u %s /bin/bash %s %s 2>&1 | tee -a /iscm-ansible-%s.log" % (ansi_user, ansi_script, self.run_name, self.run_name)
          )
        }
      },
      "_ansible_execute_run_%s" % self.run_name);
