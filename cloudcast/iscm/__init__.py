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
    def __init__(self, context=None, modules=None):
        self.userdata_elems = []
        self.metadata = {}
        # Load the context
        if context is None: context = {}
        self.context = context
        # Install the specified modules into this iscm instance
        if modules is None: modules = []
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

    def context_lookup(self, vars):
        """
        Lookup the variables in the provided dictionary, resolve with entries
        in the context
        """
        for (k,v) in vars.items():
            if isinstance(v, IscmExpr):
                vars[k] = v.resolve(self.context)

    def apply_to(self, launchable):
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

    @classmethod
    def parse_context(cls, context_def, context):
        # Examine each entry in context_def
        for (k,v) in context_def.items():
            if v["required"] and not context.has_key(k):
                raise KeyError("Context doesn't contain required var %s" % k)
            if not v["required"] and (not context.has_key(k) or context[k] is None):
                if v["default"] is not None:
                    context[k] = v["default"]
        return context


class IscmExpr(object):
    """
    Expressions are used while defining module variables. This allows us to
    perform substitutions based on the context passed to the main ISCM obj.
    """
    def resolve(self, context):
        raise NotImplementedError("Abstract class")

class IscmQExpr(IscmExpr):
    """
    Simple string expression, i.e. "{{ var }}" resolves to "value", when
    context is { "var": "value" }
    """
    def __init__(self, q):
        self.q = q
    def resolve(self, context):
        from dq import query
        return query(self.q, context)

class IscmJoinExpr(IscmExpr):
    """
    Maps to CloudFormation's join function, just making sure that we first parse
    each of the joined members through the context lookup
    """
    def __init__(self, token, *members):
        self.token = token
        self.members = members
    def resolve(self, context):
        from cloudcast.template import join as cfnjoin
        members = map(lambda m: isinstance(m,IscmExpr) and m.resolve(context) or m, self.members)
        return cfnjoin(self.token, *members)

def q(query):
    """
    Wrapper around IscmQExpr
    """
    return IscmQExpr(query)

def join(token, *members):
    """
    Wrapper around IscmJoinExpr
    """
    return IscmJoinExpr(token, *members)

class context_var:
    """
    Class containing static methods that help with the definition of context
    vars (required/optional with default value)
    """
    @classmethod
    def required(cls):
        return { "required": True }
    @classmethod
    def optional(cls, default):
        return { "required": False, "default": default }