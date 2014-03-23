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
        return str(self.definition)

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
    def resolve(self, stack, element):
        self.resolvedTo = element.ref_name

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
        return lambda: \
            CfnSimpleExpr({"Fn::FindInMap" :
                [ self.ref_name, key1, key2 ]
            })
            
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
        # By default all kwargs are properties
        properties = copy.copy(kwargs)
        # Except metadata, it is an element attribute of its own
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
        def walk_values(obj):
            if type(obj) == dict:
                for v in obj.values():
                    for vv in walk_values(v): yield vv
            elif type(obj) in [ list, tuple, set ]:
                for v in obj:
                    for vv in walk_values(v): yield vv
            else:
                yield obj
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
        return lambda: \
            CfnSimpleExpr({"Fn::GetAtt" : [ self.ref_name, key ]})


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

class EC2Instance(LaunchableResource):
    def __init__(self, **kwargs):
        LaunchableResource.__init__(self, "AWS::EC2::Instance", **kwargs)

class EC2LaunchConfiguration(LaunchableResource):
    def __init__(self, **kwargs):
        LaunchableResource.__init__(self, "AWS::AutoScaling::LaunchConfiguration", **kwargs)
