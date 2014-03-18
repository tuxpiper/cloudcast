#!/usr/bin/python

import string

class ISCM(object):
    """
    Instance Software Configuration Management, this class helps us to
    configure software in an instance. ISCM achieves this aim by 
    providing a kernel of functionality, that specialized ISCM modules
    can use in order to install, configure themselves and perform
    their duty on boot.
    All the ISCM operations here are pretty simple, and generally
    limited to the scope of what can be done solely within
    CloudFormation.
    """
    def __init__(self, modules=[]):
        self.userdata_elems = []
        self.metadata = {}
        # Install the specified modules into this iscm instance
        for mod in modules:
            mod.install(self)
        # Deploy each module into this iscm, so necessary changes to the
        # cloudformation template are computed
        for mod in reversed(modules):
            mod.deploy(self)

    def iscm_ud_append(self, *userdata):
        """
        Append elements to userdata
        """
        self.userdata_elems += list(userdata)

    def iscm_md_get(self, keypath):
        current = self.metadata
        for k in string.split(keypath, "."):
            if type(current) != dict or not current.has_key(k):
                return None
            current = current[k]
        return current

    def iscm_md_update_dict(self, keypath, data):
        """
        Update a metadata dictionary entry
        """
        current = self.metadata
        for k in string.split(keypath, "."):
            if not current.has_key(k):
                current[k] = {}
            current = current[k]
        current.update(data)

    def iscm_md_append_array(self, arraypath, member):
        """
        Append a member to a metadata array entry
        """
        array_path = string.split(arraypath, ".")
        array_key = array_path.pop()
        current = self.metadata
        for k in array_path:
            if not current.has_key(k):
                current[k] = {}
            current = current[k]
        if not current.has_key(array_key):
            current[array_key] = []
        if not type(current[array_key]) == list:
            raise KeyError("%s doesn't point to an array" % arraypath)
        current[array_key].append(member)

    def applyTo(self, launchable):
        """
        Apply this ISCM configuration into a launchable resource, such as
        an EC2 instance or an AutoScalingGroup LaunchConfig.
        """
        # Update user data
        if launchable.get_property("UserData") is not None:
            raise NotImplementedError("It's not yet supported to append SCM to existing userdata")
        user_data = {
            "Fn::Base64" : {
                "Fn::Join" : ["", [
                    "\n".join([
                        r'#!/bin/bash',
                        r'FATAL() { code=$1; shift; echo "[FATAL] $*" >&2; exit $code; }',
                        r'ERROR() { echo "[ERROR] $*" >&2 ; }',
                        r'WARN()  { echo "[WARNING] $*" >&2 ; }',
                        r'INFO()  { echo "[INFO] $*" >&2 ; }',
                        r'{',
                        r'INFO "CloudCast ISCM booting on $(date)"',
                        "\n\n"
                        ])
                ] + self.userdata_elems + [
                    "\n".join([
                        '\nINFO "CloudCast ISCM successfully completed on $(date)"',
                        '} 2>&1 | tee -a /iscm.log\n'
                    ])
                ] ]
            } 
        }
        launchable.add_property("UserData", user_data)

        # Set meta data keys
        for k in self.metadata:
            if launchable.get_metadata_key(k) is not None:
                raise NotImplementedError("It's not yet supported to append to existing metadata keys")
            launchable.add_metadata_key(k, self.metadata[k])
