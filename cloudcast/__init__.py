'''
Tools for loading and processing CloudCast templates into CloudFormation JSON templates

@author: David Losada Carballo <david@tuxpiper.com>
'''
import json, os.path
from cloudcast.elements import *

def _caller_folder():
    """
    Returns the folder where the code of the caller's caller lives
    """
    import inspect
    caller_file = inspect.stack()[2][1]
    if os.path.exists(caller_file):
        return os.path.abspath(os.path.dirname(caller_file))
    else:
        return os.path.abspath(os.getcwd())

def _run_resources_file(path, stack):
    """
    With a bit of import magic, we load the given path as a python module,
    while providing it access to the given stack under the import name '_context'.
    This function returns the module's global dictionary.
    """
    import imp, sys, random, string, copy
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
    old_path = copy.copy(sys.path)
    # Save the modules list, in order to remove modules loaded after this point
    old_sys_modules = sys.modules.keys()
    # Run the module
    # Prepare import environment
    abspath = os.path.abspath(path)
    sys.meta_path.append(ContextImporter())
    sys.path.append(os.path.dirname(abspath))   # Enable importing files within module's folder
    # Perform the importing
    srcf = open(abspath, "r")
    module_name = ''.join(random.choice(string.digits + string.lowercase) for i in range(16))
    srcmodule = imp.load_source("cloudcast._template_" + module_name, abspath, srcf)
    srcf.close()
    # Restore meta path, modules list and return module
    sys.meta_path = old_meta_path
    sys.path = old_path
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

class _stackElements(object):
    """
    This class is a glorified dictionary of stack's elements
    """
    def __init__(self):
        self.elements = {}
        self.Parameters = []
        self.Mappings = []
        self.Resources = []
        self.Outputs = []
        self.launchables = []

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
        # If the resource is launchable, keep track
        if isinstance(the_el, LaunchableResource):
            self.launchables.append(the_el)

    def dump_to_template_obj(self, stack, t):
        """
        Add resource definitions to the given template object
        """
        if len(self.Parameters) > 0:
            t['Parameters'] = dict([e.contents(stack) for e in self.Parameters])
        if len(self.Mappings) > 0:
            t['Mappings'] = dict([e.contents(stack) for e in self.Mappings])
        if len(self.Resources) > 0:
            t['Resources'] = dict([e.contents(stack) for e in self.Resources])
        if len(self.Outputs) > 0:
            t['Outputs'] = dict([e.contents(stack) for e in self.Outputs])

class Stack(object):
    """
    A stack template, transformable into JSON to upload to AWS CloudFormation, instrumentable for management
    """    
    def __init__(self, **kwargs):
        self.base_dir = None
        self.description = None
        self.required_capabilities = []
        self.env = {}
        self.elements = _stackElements()
        # Obtain base dir of the caller, if available
        self.base_dir = _caller_folder()
        # Process kwargs
        if kwargs.has_key("description"):
            self.description = kwargs["description"]
        if kwargs.has_key("env"):
            self.env = _env_dict(kwargs["env"])
        if kwargs.has_key("resources_file"):
            self.load_resources(kwargs["resources_file"])

    def add_element(self, element, name):
        self.elements.name_stack_element(element, name)
        self.elements.add_stack_element(element)

    def add_required_capability(self, cap):
        if cap not in self.required_capabilities:
            self.required_capabilities.append(cap)

    def load_resources(self, path):
        if not os.path.isabs(path):
            # Search relative to the caller, the stack and cwd
            search_paths = [
                os.path.join(_caller_folder(), path),
                os.path.join(self.base_dir, path),
                os.path.join(os.getcwd(), path)
            ]
            for p in search_paths:
                if os.path.isfile(p):
                    path = p
                    break
                # if path doesn't exist the function below will fail anyway
        #
        self.elements.load_template_srcmodule(self, path)

    def has_element(self, name):
        return self.elements.elements.has_key(name)

    def get_element(self, name):
        return self.elements.elements[name]

    def get_launchable_resources(self):
        return self.elements.launchables

    def fix_broken_references(self, placeholder="#!broken_ref!#"):
        for val in self.elements.elements:
            if isinstance(val, StackElement):
                # Check if the element belongs to this stack
                el_name = val.ref_name
                if not self.has_element(el_name) or not self.get_element(el_name) == val:
                    raise RuntimeError("Broken reference: " + str(val))
        
    def dump_json(self, pretty=True):
        """
        Return a string representation of this CloudFormation template.
        """
        # Build template
        t = {}
        t['AWSTemplateFormatVersion'] = '2010-09-09'        
        if self.description is not None:
            t['Description'] = self.description
        self.elements.dump_to_template_obj(self, t)

        return _CustomJSONEncoder(indent=2 if pretty else None,
                                  sort_keys=False).encode(t)                                    
      
class _env_dict(dict):
    def __init__(self, *args, **kw):
        super(_env_dict,self).__init__(*args, **kw)
    def required(self, key):
        if not self.has_key(key):
            raise KeyError("The stack environment doesn't contain the required entry %s" % key)
        return self[key]
    def optional(self, key, default=None):
        if not self.has_key(key):
            return default
        else:
            return self[key]
