#!/usr/bin/env python

import os.path
from cloudcast._utils import caller_folder, search_file
from cloudcast.template import AWS, Resource

_shellinit_file = os.path.join(os.path.dirname(__file__), "scripts", "init.sh")

class Shell(object):
    """
    Configure an instance using shell scripts
    """
    def __init__(self, scripts=None, **kwargs):
        if kwargs.has_key("shell_vars"):
            self.shell_vars = kwargs["shell_vars"]
        else:
            self.shell_vars = {}
        #
        if kwargs.has_key("name"):
            self.name = kwargs["name"] 
        else:
            self.name = None
        #
        if not kwargs.has_key("script_paths"):
            self.script_paths = [ caller_folder(), os.getcwd() ]
        #
        # Add user provided scripts
        self.init_scripts = [ Shell.runScript(_shellinit_file) ]
        if kwargs.has_key("init_scripts"):
            self.init_scripts += kwargs["init_scripts"]
        self.scripts = []
        if scripts is not None:
            self.scripts = scripts

    def install(self, iscm):
        # This iscm module uses the cfn-init module to deploy and execute
        # its payload. If it's not installed 
        if not hasattr(iscm, "iscm_cfninit_add_config"):
            raise RuntimeError("The Shell ISCM module depends on the CfnInit module to be installed in the same chain")

    def _load_scripts(self, script_list, script_content=None):
        # Concatenate scripts contents
        if script_content is None:
            script_content = ""

        for script in script_list:
            if script['type'] == "file":
                script_path = search_file(script['path'], *self.script_paths)
                if script_path is None:
                    raise RuntimeError("Unable to find script in path %s" % script['path'])
                with open(script_path, "r") as f:
                    data = f.read()
                    # Ensure trailing new line
                    if data[-1] != "\n": data += "\n"
                    script_content += data
            else:
                raise RuntimeError("Unhandled script type: %s" % script['type'])

        return script_content

    def deploy(self, iscm):
        # If no name has been given for this shell iscm, assign one sequentially
        if self.name is None:
            last_anonymous_k = iscm.iscm_get_var("shell_iscm::last_anonymous_k")
            if last_anonymous_k is None:
                last_anonymous_k = 0
            last_anonymous_k += 1
            self.name = "shell_%d" % last_anonymous_k
            iscm.iscm_set_var("shell_iscm::last_anonymous_k", last_anonymous_k)

        # Create a metadata entry that holds the relationship between variable names and their values
        if self.shell_vars:
            shell_vars_md_entry = "shell_iscm.instances.%s" % self.name
            self.shell_vars = iscm.context_lookup(self.shell_vars)        # resolve references to iscm context
            iscm.iscm_md_update_dict(shell_vars_md_entry, { "vars": self.shell_vars })
            shell_vars_md_entry += ".vars"
        else:
            shell_vars_md_entry = ""

        # Create script file with all initialization scripts code
        init_script_path = "/root/shell-iscm/init-%s.sh" % self.name
        init_script_content = self._load_scripts(self.init_scripts)

        # Collect all scripts' code, starting with the shebang and processing the init scripts
        script_content = \
            '#!/bin/bash\n' + \
            '. %s\n' % init_script_path

        script_content = self._load_scripts(self.scripts, script_content)
        # Add cfn-init config to write and execute the user specified scripts
        stack_user_key = iscm.iscm_cfninit_get_stack_user_key()
        shell_config = {
            "files": {
                init_script_path : {
                    "content": {
                        "Fn::Join" : ["", [ 
                            'export AWS__STACK_NAME="', AWS.StackName ,'" ',
                            'AWS__STACKEL_NAME="', Resource.ThisName() , '" ',
                            'AWS__BOOTSTRAP_KEY_ID="', stack_user_key , '" ',
                            'AWS__BOOTSTRAP_SECRET_KEY="', stack_user_key["SecretAccessKey"] , r'" ',
                            'AWS__REGION="', AWS.Region , '"\n\n',
                            'SHELL_ISCM_NAME="%s"\n' % self.name,
                            'SHELL_ISCM_METADATA_VARS_KEY="%s"\n' % shell_vars_md_entry,
                            'SHELL_ISCM_INIT_SCRIPT="%s"\n' % init_script_path,
                            init_script_content
                        ] ]
                    },
                    "mode": "000700",
                    "owner": "root",
                    "group": "root"
                },
                "/root/shell-iscm/%s.sh" % self.name: {
                    "content": script_content,
                    "mode": "000700",
                    "owner": "root",
                    "group": "root"
                }
            },
            "commands": {
                "runit": {
                    "command": "/root/shell-iscm/%s.sh  2>&1 | tee -a /iscm-shell.log" % self.name
                }
            }
        }
        iscm.iscm_cfninit_add_config(shell_config)

    @classmethod
    def runScript(cls, path):
        return { "type": "file", "path": path }