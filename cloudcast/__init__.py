'''
Tools for loading and processing CloudCast templates into CloudFormation JSON templates

@author: David Losada Carballo <david@tuxpiper.com>
'''
import json
from cloudcast.elements import *

def _run_resources_file(path, stack):
    """
    With a bit of import magic, we load the given path as a python module,
    while providing it access to the given stack under the import name '_context'.
    This function returns the module's global dictionary.
    """
    import imp, os.path, sys, random, string, copy
    class ContextImporter(object):
        def find_module(self, fullname, path=None):
            if fullname == '_context':
                self.path = path
                return self
            return None
        def load_module(self, name):
            mod = imp.new_module("_context")
            mod.stack = stack
            return mod
    # Temporarily add the context importer into the meta path
    old_meta_path = copy.copy(sys.meta_path)
    sys.meta_path.append(ContextImporter())
    # Save the modules list, in order to remove modules loaded here
    old_sys_modules = sys.modules.keys()
    # Run the module
    abspath = os.path.abspath(path)
    srcf = open(abspath, "r")
    module_name = ''.join(random.choice(string.digits + string.lowercase) for i in range(16))
    srcmodule = imp.load_source("cloudcast._template_" + module_name, abspath, srcf)
    srcf.close()
    # Restore meta path, modules list and return module
    sys.meta_path = old_meta_path
    for modname in sys.modules.keys():
        if not modname in old_sys_modules:
            del sys.modules[modname]
    return srcmodule
    

class _CustomJSONEncoder(json.JSONEncoder):
    """
    Extended JSON encoder, it handles references to stack elements
    and callables
    """
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
    def default(self, o):
        if hasattr(o, 'cfn_expand'):
            return o.cfn_expand()
        elif hasattr(o, '__call__'):
            return o.__call__()
        else:
            return super(self.__class__, self).default(o)

class _StackResources(object):
    """
    This class is a dictionary of stack's AWS resources
    """
    def __init__(self):
        self.elements = {}
        self.Parameters = []
        self.Mappings = []
        self.Resources = []
        self.Outputs = []

    def load_template_srcmodule(self, stack, path):
        """
        This function actually fills the stack with definitions coming from a template file
        """
        srcmodule = _run_resources_file(path, stack)
        # Process the loaded module and find the stack elements
        elements = self.find_stack_elements(srcmodule)
        elements = sorted(elements, key=lambda x: x[:-1])
        # Assign a name to each element and add to our dictionaries
        for (module_name, el_name, element) in elements:
            full_name = self.generate_cfn_name(module_name, el_name)
            self.name_stack_element(element, full_name)
            self.add_stack_element(element)
        
    def find_stack_elements(self, module, module_name="", _visited_modules=None):
        """
        This function goes through the given container and returns the stack elements. Each stack
        element is represented by a tuple:
            ( container_name, element_name, stack_element)
        The tuples are returned in an array
        """
        from types import ModuleType
        if _visited_modules is None: _visited_modules = []
        _visited_modules.append(module)
        #
        elements = []
        for el_name in dir(module):
            the_el = module.__getattribute__(el_name)
            if isinstance(the_el, ModuleType):
                # Recursively go into the module
                if the_el in _visited_modules:
                    continue
                elements = elements + self.find_stack_elements(the_el, module_name + el_name + ".", _visited_modules)
            elif isinstance(the_el, StackElement):
                # Add to list
                elements.append((module_name, el_name, the_el))
        return elements
    
    def generate_cfn_name(self, module_name, el_name):
        import re
        normalized_el_name = re.sub(r'[^a-zA-Z0-9]', '0', el_name)
        if self.elements.has_key(normalized_el_name):
            # Use the module name
            normalized_module_name = re.sub(r'[^a-zA-Z0-9.]', '0', module_name)
            return normalized_module_name.replace(".", "XX") + normalized_el_name
        else:
            return normalized_el_name
            
    def name_stack_element(self, the_el, name):
        # A given element can only be assigned a name once!
        if the_el.ref_count > 0:
            raise Exception("%s is a second reference (first one was: %s)" % (name, the_el.ref_name))
        # Give name to the stack element so he knows how to reference
        # itself within the stack template
        the_el.ref_count += 1
        the_el.ref_name = name
            
    def add_stack_element(self, the_el):
        # If the element doesn't want to be dumped, do nothing
        if the_el.dont_dump:
            return
        # Add to our dictionary of elements
        if self.elements.has_key(the_el.ref_name):
            if self.elements[the_el.ref_name] == the_el:
                # Repeated name -> element mapping, skip
                return
            else:
                raise Exception("%s is a an element name used elsewhere!!" % the_el.ref_name)
        self.elements[the_el.ref_name] = the_el
        # Add contents of the element to the corresponding section
        # of the stack
        if isinstance(the_el, Parameter):
            self.Parameters.append(the_el)
        elif isinstance(the_el, Mapping) and the_el.is_used:
            self.Mappings.append(the_el)
        elif isinstance(the_el, Output):
            self.Outputs.append(the_el)
        elif isinstance(the_el, Resource):
            self.Resources.append(the_el)

    def dump_to_template_obj(self, t):
        """
        Add resource definitions to the given template object
        """
        if len(self.Parameters) > 0:
            t['Parameters'] = dict([e.contents(self) for e in self.Parameters])
        if len(self.Mappings) > 0:
            t['Mappings'] = dict([e.contents(self) for e in self.Mappings])
        if len(self.Resources) > 0:
            t['Resources'] = dict([e.contents(self) for e in self.Resources])
        if len(self.Outputs) > 0:
            t['Outputs'] = dict([e.contents(self) for e in self.Outputs])

class Stack(object):
    """
    A stack template, transformable into JSON to upload to AWS CloudFormation, instrumentable for management
    """    
    def __init__(self, **kwargs):
        self.description = None
        self.required_capabilities = []
        self.env = {}
        self.resources = _StackResources()
        #
        if kwargs.has_key("description"):
            self.description = kwargs["description"]
        if kwargs.has_key("env"):
            self.env = kwargs["env"]
        if kwargs.has_key("resources_file"):
            self.load_resources(kwargs["resources_file"])

    def add_required_capability(self, cap):
        if cap not in self.required_capabilities:
            self.required_capabilities.append(cap)

    def load_resources(self, path):
        self.resources.load_template_srcmodule(self, path)

    def has_resource(self, name):
        """
        """
        raise NotImplementedError

    def get_resource(self, name):
        """
        """
        raise NotImplementedError
        
    def dump_json(self, pretty=True):
        """
        Return a string representation of this CloudFormation template.
        """
        # Build template
        t = {}
        t['AWSTemplateFormatVersion'] = '2010-09-09'        
        if self.description is not None:
            t['Description'] = self.description
        self.resources.dump_to_template_obj(t)

        return _CustomJSONEncoder(indent=2 if pretty else None,
                                  sort_keys=False).encode(t)                                    
      