#!/usr/bin/env python
import copy, types

_default_get_pip_url = "https://raw.github.com/pypa/pip/master/contrib/get-pip.py"
_default_aws_cfn_bootstrap_url = "https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-1.3.14.tar.gz"

from cloudcast.template import AWS, Resource

class CfnInit(object):
    """
    Configure an instance using cfn-init
       ( http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-init.html ,
         http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-init.html )
    This class makes sure that the tools are installed, and that they are
    provided with the right credentials, so they can acess the instance metadata
    """
    def __init__(self, stack_user_key, **kwargs):
        self.configs = {}
        self.config_names = []      # Keeps runtime order of configs
        self.unnamed_config_k = 0   # We use this to name configs with no name
        #
        # Take care of some bootstrapping params here
        self.stack_user_key = stack_user_key
        self.get_pip_url = _default_get_pip_url
        self.aws_cfn_bootstrap_url = _default_aws_cfn_bootstrap_url
        if kwargs.has_key("get_pip_url"):
            self.get_pip_url = kwargs['get_pip_url']
        if kwargs.has_key("aws_cfn_bootstrap_url"):
            self.aws_cfn_bootstrap_url = kwargs["aws_cfn_bootstrap_url"]
        #
        # Load configs if provided
        if kwargs.has_key("configs"):
            if type(kwargs["configs"]) in (list, tuple, set):
                for config in kwargs["configs"]:
                    self.iscm_cfninit_add_config(config)
            elif type(kwargs["configs"]) == dict:
                for (name,config) in kwargs["configs"].iteritems():
                    self.iscm_cfninit_add_config(config, name=name)
            else:
                raise RuntimeError("Unrecognized container for configs")

    def iscm_cfninit_add_config(self, config, name=None):
        if name == "configSets":
            raise RuntimeError("Reserved config name 'configSets' can't be used")
        if name is None:
            name = "cfninit_%03d" % self.unnamed_config_k
            self.unnamed_config_k += 1
        if self.configs.has_key(name):
            raise RuntimeError("cfn-init config with name %s already exists") % name
        self.configs[name] = config
        self.config_names.append(name)

    def iscm_cfninit_get_stack_user_key(self):
        return self.stack_user_key

    def install(self, iscm):
        # Load iscm with our methods so they are available to other iscm classes
        if not hasattr(iscm, "iscm_cfninit_add_config"):
            import types
            iscm_cfninit = self
            def wrapper_1(self, config, name=None):
                iscm_cfninit.iscm_cfninit_add_config(config, name)
            iscm.iscm_cfninit_add_config = types.MethodType(wrapper_1, iscm)
        if not hasattr(iscm, "iscm_cfninit_get_stack_user_key"):
            import types
            iscm_cfninit = self
            def wrapper_2(self):
                return iscm_cfninit.iscm_cfninit_get_stack_user_key()
            iscm.iscm_cfninit_get_stack_user_key = types.MethodType(wrapper_2, iscm)
        #
        # Add scripting into user data, which will make sure that
        # the cfn-init tools are installed.
        iscm.iscm_ud_append(
            "\n".join([
                r'[ -z "`which python`" ] && FATAL 1 "Unable to find python"',
                r'[ -z "`which pip`" ] && [ ! -x /usr/local/bin/pip ] && { curl %s | python; }' % self.get_pip_url,
                r'PIP_PATH=`which pip`',
                r'PIP_PATH=${PIP_PATH:-/usr/local/bin/pip}',
                r'[ ! -x "$PIP_PATH" ] && FATAL 1 "Unable to find/install pip, which is required"',
                r'$PIP_PATH install %s || FATAL 1 "Unable to install cfn-init tools"' % self.aws_cfn_bootstrap_url,
            ]),
            "\n",
            'export AWS__STACK_NAME="', AWS.StackName ,'" ',
                   'AWS__STACKEL_NAME="', Resource.ThisName() , '" ',
                   'AWS__BOOTSTRAP_KEY_ID="', self.stack_user_key , '" ',
                   'AWS__BOOTSTRAP_SECRET_KEY="', self.stack_user_key["SecretAccessKey"] , r'" ',
                   'AWS__REGION="', AWS.Region , '"\n',
            r'cfn-init -v -s "$AWS__STACK_NAME" -r "$AWS__STACKEL_NAME" --region "$AWS__REGION" --access-key "$AWS__BOOTSTRAP_KEY_ID" --secret-key "$AWS__BOOTSTRAP_SECRET_KEY"',
             ' || FATAL 1 "cfn-init unsuccessful"\n',
        )

    def deploy(self, iscm):
        #
        # Load configs into the resource metadata, so cfn-init can find them
        # on runtime and get them done
        cfninit_metadata = self.configs
        cfninit_metadata.update({
            "configSets": {
                "default": self.config_names
            }
        })
        iscm.iscm_md_update_dict("AWS::CloudFormation::Init", cfninit_metadata)
