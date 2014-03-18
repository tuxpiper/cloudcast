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
		self.scripts = []
		if scripts is not None:
			self.scripts += scripts

	def install(self, iscm):
		# This iscm module uses the cfn-init module to deploy and execute
		# its payload. If it's not installed 
		if not hasattr(iscm, "iscm_cfninit_add_config"):
			raise RuntimeError("The Shell ISCM module depends on the CfnInit module to be installed in the same chain")
		with open(_shellinit_file, "r") as f:
			init_data = f.read()
		#
		# Add config for writing the iscm-shell
		stack_user_key = iscm.iscm_cfninit_get_stack_user_key()
		iscm_config = {
			"files": {
				"/root/shell-iscm/_init.sh" : {
					"content": {
						"Fn::Join" : ["", [ 
							'export AWS__STACK_NAME="', AWS.StackName ,'" ',
							'AWS__STACKEL_NAME="', Resource.ThisName() , '" ',
							'AWS__BOOTSTRAP_KEY_ID="', stack_user_key , '" ',
							'AWS__BOOTSTRAP_SECRET_KEY="', stack_user_key["SecretAccessKey"] , r'" ',
							'AWS__REGION="', AWS.Region , '"\n\n',
							init_data
						] ]
					},
					"mode": "000700",
					"owner": "root",
					"group": "root"
				}
			}
		}
		iscm.iscm_cfninit_add_config(iscm_config, "iscm-shell-init")

	def deploy(self, iscm):
		# If no name has been given for this shell iscm, assign one sequentially
		if self.name is None:
			last_anonymous_k = iscm.iscm_md_get("shell_iscm.last_anonymous_k")
			if last_anonymous_k is None:
				last_anonymous_k = 0
			last_anonymous_k += 1
			self.name = "shell_%d" % last_anonymous_k
			iscm.iscm_md_update_dict("shell_iscm", { "last_anonymous_k": last_anonymous_k })

		# Create a metadata entry that holds the relationship between variable names and their values
		iscm.iscm_md_update_dict("shell_iscm.instances.%s" % self.name, { "vars": self.shell_vars })

		# Collect all scripts' code, we start with some basic definitions
		script_content = \
		    r'#!/bin/bash' + "\n" + \
			r'SHELL_ISCM_NAME="%s"' % self.name + "\n" + \
			r'SHELL_ISCM_METADATA_VARS_KEY="shell_iscm.instances.%s.vars"' % self.name + "\n" + \
			r'. /root/shell-iscm/_init.sh' + "\n\n"

		for script in self.scripts:
			if script['type'] == "file":
				script_path = search_file(script['path'], *self.script_paths)
				if script_path is None:
					raise RuntimeError("Unable to find script in path %s" % script['path'])
				with open(script_path, "r") as f:
					data = f.read()
					# Ensure trailing new line
					if data[-1] != "\n": data += "\n"
					script_content += data

		# Add cfn-init config to get the stuff done
		shell_config = {
			"files": {
				"/root/shell-iscm/%s.sh" % self.name: {
					"content": script_content,
					"mode": "000700",
					"owner": "root",
					"group": "root"
				}
			},
			"commands": {
				"runit": {
					"command": "/root/shell-iscm/%s.sh" % self.name
				}
			}
		}
		iscm.iscm_cfninit_add_config(shell_config)

	@classmethod
	def runScript(cls, path):
		return { "type": "file", "path": path }