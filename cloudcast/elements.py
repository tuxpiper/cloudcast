'''
Basic definition of the elements available for building CloudFormation stack templates

@author: David Losada Carballo <david@tuxpiper.com>
'''

import copy

class CfnSimpleExpr(object):
    """
    A static CloudFormation expression (i.e { "Ref" : "AWS::StackName" })
    """
    def __init__(self, definition):
        self.definition = definition
    def cfn_expand(self):
        return self.definition
    def __repr__(self):
        return "<CfnSimpleExpr: '%s'>" % self.definition

class CfnGetAttrExpr(object):
    def __init__(self, el, attr):
        self.el = el
        self.attr = attr
    def cfn_expand(self):
        return CfnSimpleExpr({"Fn::GetAtt" : [ self.el.ref_name, self.attr ]})
    def __repr__(self):
        return "<CfnGetAttrExpr: '%s', '%s'>" % (self.el.ref_name, self.attr)

class GetRefNameExpr(object):
    """
    An expression that returns the name of the given element
    """
    def __init__(self, element):
        self.element = element
    def cfn_expand(self):
        return self.element.ref_name
    def __repr__(self):
        return "<GetRefNameExpr: '%s', '%s'>" % self.element.ref_name


class CfnRegionExpr(object): 
    def cfn_expand(self):
        return { "Ref" : "AWS::Region" }
    def resolve(self, stack=None, element=None, cfn_env=None):
        if cfn_env.has_key("region"):
            return cfn_env["region"]
    def __repr__(self):
        return "<CfnRegionExpr>"

class CfnSelectExpr(object):
    def __init__(self, listOfObjects, index):
        self.listOfObjects = listOfObjects
        self.index = index
    def cfn_expand(self):
        listOfObjects = self.listOfObjects
        index = self.index
        #
        if hasattr(listOfObjects, "cfn_expand"):
            listOfObjects = listOfObjects.cfn_expand()
        if hasattr(index, "cfn_expand"):
            index = index.cfn_expand()
        #
        return CfnSimpleExpr({"Fn::Select": [ index, listOfObjects ]})

class MappingLookupExpr(object):
    """
    An expression that performs lookup in a mapping
    """
    def __init__(self, mapping, key1, key2):
        self.mapping = mapping
        self.key1 = key1
        self.key2 = key2
    def cfn_expand(self):
        return {"Fn::FindInMap" : [ self.mapping.ref_name, self.key1, self.key2 ]}
    def resolve(self, stack=None, element=None, cfn_env=None):
        keyval1 = self.key1
        keyval2 = self.key2
        if hasattr(keyval1, "resolve"):
            keyval1 = keyval1.resolve(stack, element, cfn_env)
        if hasattr(keyval2, "resolve"):
            keyval2 = keyval2.resolve(stack, element, cfn_env)
        return self.mapping.el_attrs[keyval1][keyval2]
    def __repr__(self):
        return "<MappingLookupExpr: '%s', '%s', '%s'>" % (self.mapping.ref_name, self.key1, self.key2)

def get_ref_name(element):
    return GetRefNameExpr(element)

class CloudCastHelperExpr(object):
    """
    Helper expressions are interpreted and transformed by resources before passing
    onto the CloudFormation tempalte
    """
    def resolve(self, stack, element):
        raise NotImplementedError("This is for subclasses to sort out")
    def cfn_expand(self):
        return self.resolvedTo

class ThisResourceExpr(CloudCastHelperExpr):
    """
    This expression resolves to the resource where it is contained
    """
    def resolve(self, stack=None, element=None, cfn_env=None):
        self.resolvedTo = element.ref_name
    def __repr__(self):
        return "<ThisResourceExpr>"

class StackElement(object):
    """
    Class for elements that appear in the stack definition, this includes
    parameters, resources, outputs and mappings
    """
    def __init__(self, **kwargs):
        """
        Creates the stack element, copying the provided properties
        """
        self.ref_name = None    # Reference name in template module
        self.ref_count = 0      # Only one reference allowed
        self.el_attrs = copy.copy(kwargs)
        self.dont_dump = False  # Avoids dumping the element when transformning
        # Filter out any attributes with value None
        self.el_attrs = dict(filter(lambda(k,v): v is not None, self.el_attrs.iteritems()))

    def contents(self, stack):
        return (self.ref_name, self.el_attrs)
    
    def cfn_expand(self):
        """
        Returns AWS CloudFormation idiom for referencing the element
        """
        if self.ref_name is None:
            raise Exception("Tried to get a reference when I still don't have a name!")
        return lambda: CfnSimpleExpr({ "Ref" : self.ref_name })
    
    def __getattribute__(self, name):
        """
        Capture some attribute references.
          - 'name' returns an object that, when evaluated, will resolve to this resource's name
            within the stack template
        """
        if name == "name":
            return lambda: self.ref_name 
        else:
            return super(StackElement, self).__getattribute__(name)


class Parameter(StackElement):
    """
    Stack parameter
    """
    def __init__(self, **kwargs):
        StackElement.__init__(self, **kwargs)

class Mapping(StackElement):
    """
    Stack mapping.
    """    
    def __init__(self, mapping):
        StackElement.__init__(self, **mapping)
        self.is_used = False
    
    def find(self, key1, key2):
        self.is_used = True
        return MappingLookupExpr(self, key1, key2)
            
class Output(StackElement):
    """
    Stack output
    """
    pass

class Resource(StackElement):
    """
    Stack resource
    """
    @classmethod
    def ThisName(cls):
        """
        Returns a static expression that, when evaluated, will be
        resolved to the CloudFormation name of the resource where this
        expression is used. This will be just a string for CloudFormation and,
        thus, it won't be failing because of recursive element dependencies.
        """
        return ThisResourceExpr()

    def __init__(self, resource_type, **kwargs):
        self.resource_type = resource_type
        # If 'Properties' not specified, all kwargs are properties
        if not kwargs.has_key("Properties"):
            properties = copy.copy(kwargs)
            # except Metadata, it is an element attribute of its own
            if kwargs.has_key('Metadata'):
                properties.pop('Metadata')
                metadata = kwargs['Metadata']
            else:
                metadata = None
            # And DependsOn, that is also on its own
            if kwargs.has_key('DependsOn'):
                properties.pop('DependsOn')
                depends_on = kwargs['DependsOn']
            else:
                depends_on = None
            # DeletionPolicy handling
            if kwargs.has_key('DeletionPolicy'):
                properties.pop('DeletionPolicy')
                deletion_policy = kwargs['DeletionPolicy']
            else:
                deletion_policy = None
            # UpdatePolicy handling
            if kwargs.has_key('UpdatePolicy'):
                properties.pop('UpdatePolicy')
                update_policy = kwargs['UpdatePolicy']
            else:
                update_policy = None
            # UpdatePolicy handling
            StackElement.__init__(self,
                Type=resource_type,
                Metadata=metadata,
                DependsOn=depends_on,
                Properties=properties,
                DeletionPolicy = deletion_policy,
                UpdatePolicy = update_policy
            )
        else:
            StackElement.__init__(self,
                Type=resource_type,
                **copy.copy(kwargs))
        
    def add_dependency(self, dep):
        if not self.el_props.has_key("DependsOn"):
            self.el_attrs["DependsOn"] = [ dep ]
        else:
            self.el_attrs["DependsOn"].append(dep)

    def add_property(self, key, value):
        if not self.el_attrs.has_key('Properties'):
            self.el_attrs['Properties'] = {}
        self.el_attrs['Properties'][key] = value

    def get_property(self, key, default=None):
        if not self.el_attrs.has_key('Properties') or not self.el_attrs['Properties'].has_key(key):
            return default
        return self.el_attrs['Properties'][key]

    def add_metadata_key(self, key, value):
        if not self.el_attrs.has_key('Metadata'):
            self.el_attrs['Metadata'] = {}
        self.el_attrs['Metadata'][key] = value

    def get_metadata_key(self, key, default=None):
        if not self.el_attrs.has_key('Metadata') or not self.el_attrs['Metadata'].has_key(key):
            return default
        return self.el_attrs['Metadata'][key]
        
    def contents(self, stack):
        # Find and resolve helper expressions before dumping the contents
        from cloudcast._utils import walk_values
        for value in walk_values(self.el_attrs):
            if isinstance(value, CloudCastHelperExpr): value.resolve(stack, self)
        #
        # Dump the contents
        return (self.ref_name, self.el_attrs)

    def __getitem__(self, key):
        """
        [] operator for a resource element is equivalent to calling
        cloudformation's "Fn::GetAtt"
        """
        return CfnGetAttrExpr(self, key)

    def __repr__(self):
        return "<Resource('%s')>" % self.ref_name


class LaunchableResource(Resource):
    def __init__(self, restype, **kwargs):
        self.iscm = None
        if kwargs.has_key("iscm"):
            # If an SCM spec is given, build it
            from cloudcast.iscm import ISCM
            if isinstance(kwargs["iscm"], ISCM):
                self.iscm = kwargs["iscm"]
            else:
                self.iscm = ISCM(kwargs["iscm"])
            kwargs.pop("iscm")
        Resource.__init__(self, restype, **kwargs)
    
    def contents(self, stack):
        # Before "spilling the beans", let the iscm update this element
        if self.iscm is not None:
            self.iscm.apply_to(self)
        # Proceed with dumping the contents
        return Resource.contents(self, stack)

    def is_buildable(self):
        if self.iscm is None:
            return False
        return self.iscm.is_buildable()

    def resolve_ami(self, **kwargs):
        ami = self.el_attrs["Properties"]["ImageId"]
        if hasattr(ami, "resolve"):
            ami = ami.resolve(stack=None, element=self, cfn_env=kwargs)
        return ami

class EC2Instance(LaunchableResource):
    def __init__(self, **kwargs):
        LaunchableResource.__init__(self, "AWS::EC2::Instance", **kwargs)
    @classmethod
    def standalone_from_launchable(cls, launch):
        """
        Given a launchable resource, create a definition of a standalone
        instance, which doesn't depend on or contain references to other
        elements.
        """
        attrs = copy.copy(launch.el_attrs)
        # Remove attributes we overwrite / don't need
        del attrs["Type"]
        if attrs.has_key("DependsOn"):
            del attrs["DependsOn"]
        if attrs["Properties"].has_key("SpotPrice"):
            del attrs["Properties"]["SpotPrice"]
        if attrs["Properties"].has_key("InstanceMonitoring"):
            del attrs["Properties"]["InstanceMonitoring"]
        if attrs["Properties"].has_key("SecurityGroups"):
            del attrs["Properties"]["SecurityGroups"]
        if attrs["Properties"].has_key("InstanceId"):
            raise RuntimeError("Can't make instance from launchable containing InstanceId property")
        inst = EC2Instance(**attrs)
        # TODO: shallow copy?
        inst.iscm = launch.iscm
        return inst

class EC2LaunchConfiguration(LaunchableResource):
    def __init__(self, **kwargs):
        LaunchableResource.__init__(self, "AWS::AutoScaling::LaunchConfiguration", **kwargs)

class WaitCondition(Resource):
    def __init__(self, **kwargs):
        Resource.__init__(self, "AWS::CloudFormation::WaitCondition", **kwargs)

class WaitConditionHandle(Resource):
    def __init__(self, **kwargs):
        Resource.__init__(self, "AWS::CloudFormation::WaitConditionHandle", **kwargs)
