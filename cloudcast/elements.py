'''
Basic definition of the elements available for building CloudFormation stack templates

Created on Jun 13, 2013

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
    def __init__(self):
        self.value = None
    def fix_value(self, value):
        """
        It actually turns this parameter in some sort of constant, by assigning programmatically
        a value to it. This is used when including sub-stacks
        """
        if not isinstance(value, CfnSimpleExpr):
            self.value = CfnSimpleExpr(value)
        else:
            self.value = value
        self.dont_dump = True
    def cfn_get_reference(self):
        # If no value assigned, this behaves like a StackElement
        if self.value is None:
            return StackElement.cfn_get_reference(self)
        else:
            # If value assigned this behaves more like an expression
            return self.value.cf_expand()

class Mapping(StackElement):
    """
    Stack mapping.
    """    
    def __init__(self, da_map):
        StackElement.__init__(self)
        self.is_used = False
        self.the_map = da_map

    def contents(self, stack):
        return (self.ref_name, self.the_map)
    
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
    this_resource_name = '{ "CloudCast::Fn": "ToBeImplemented" }'
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
        
    def contents(self, stack):
        return (self.ref_name, self.el_attrs)

    def __getitem__(self, key):
        """
        [] operator for a resource element is equivalent to calling
        cloudformation's "Fn::GetAtt"
        """
        return lambda: \
            CfnSimpleExpr({"Fn::GetAtt" : [ self.ref_name, key ]})
