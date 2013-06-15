'''
Tools for loading and processing CloudCast templates into CloudFormation JSON templates

Created on Jun 13, 2013

@author: David Losada Carballo <david@tuxpiper.com>
'''
import json
from cloudcast.elements import *

class CustomJSONEncoder(json.JSONEncoder):
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
    
class StackTemplate:
    """
    A stack template containing all the information for a deployment
    """    
    def __init__(self, path):
        self.elements = {}
        self.Parameters = []
        self.Mappings = []
        self.Resources = []
        self.Outputs = []
        self._load_template_srcmodule(path)
        
    def _load_template_srcmodule(self, path):
        """
        This function actually fills the  
        """
        import imp, os.path, random, string
        from cloudcast import stack
        
        reload(stack)   # This is reloaded every time a template is loaded
        abspath = os.path.abspath(path)
        srcf = open(abspath, "r")
        module_name = ''.join(random.choice(string.digits + string.lowercase) for i in range(16))
        srcmodule = imp.load_source("cloudcast._template_" + module_name, abspath, srcf)
        # Process the loaded module and find the stack elements
        elements = self._find_stack_elements(srcmodule)
        elements = sorted(elements, key=lambda x: x[:-1])
        # Assign a name to each element and add to our dictionaries
        for (module_name, el_name, element) in elements:
            full_name = self._generate_cfn_name(module_name, el_name)
            self._name_stack_element(element, full_name)
            self._add_stack_element(element)
        
    def _find_stack_elements(self, module, module_name=""):
        """
        This function goes through the given container and returns the stack elements. Each stack
        element is represented by a tuple:
            ( container_name, element_name, stack_element)
        The tuples are returned in an array
        """
        self._visited_modules = [ module ];
        from types import ModuleType
        elements = []
        for el_name in dir(module):
            the_el = module.__getattribute__(el_name)
            if isinstance(the_el, ModuleType):
                # Recursively go into the module
                if the_el in self._visited_modules:
                    continue
                elements = elements + self._find_stack_elements(the_el, module_name + el_name + ".")
            elif isinstance(the_el, StackElement):
                # Add to list
                elements.append((module_name, el_name, the_el))
        return elements
    
    def _generate_cfn_name(self, module_name, el_name):
        import re
        normalized_el_name = re.sub(r'[^a-zA-Z0-9]', '0', el_name)
        if self.elements.has_key(normalized_el_name):
            # Use the module name
            normalized_module_name = re.sub(r'[^a-zA-Z0-9.]', '0', module_name)
            return normalized_module_name.replace(".", "XX") + normalized_el_name
        else:
            return normalized_el_name
            
    
    def _name_stack_element(self, the_el, name):
        # A given element can only be assigned a name once!
        if the_el.ref_count > 0:
            raise Exception("%s is a second reference (first one was: %s)" % (name, the_el.ref_name))
        # Give name to the stack element so he knows how to reference
        # itself within the stack template
        the_el.ref_count += 1
        the_el.ref_name = name
            
    def _add_stack_element(self, the_el):
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
        
    def dump_json(self, pretty=True):
        """
        Return a string representation of this CloudFormation template.
        """
        from cloudcast import stack
        # Build template
        t = {}
        t['AWSTemplateFormatVersion'] = '2010-09-09'        
        if stack.get_description() is not None:
            t['Description'] = stack.get_description()
        if len(self.Parameters) > 0:
            t['Parameters'] = dict([e.contents(self) for e in self.Parameters])
        if len(self.Mappings) > 0:
            t['Mappings'] = dict([e.contents(self) for e in self.Mappings])
        if len(self.Resources) > 0:
            t['Resources'] = dict([e.contents(self) for e in self.Resources])
        if len(self.Outputs) > 0:
            t['Outputs'] = dict([e.contents(self) for e in self.Outputs])

        return CustomJSONEncoder(indent=2 if pretty else None,
                                  sort_keys=False).encode(t)                                    
      
        
def prepare_user_data(ud):
    # This function parses %%{ cfn-json }%% escapes
    # The returned array's even positions contain CFN-json escapes
    def split_escapes(s):
        sp = s.split("%%{", 1)
        if len(sp) == 1:
            return sp
        else:
            fsp = sp[1].split("}%%",1)
            if len(fsp) == 1:
                raise Exception("Unclosed %%{}%% escape!")
            return [ sp[0], eval("{" + fsp[0] + "}") ] + split_escapes(fsp[1])
    # Process each user data line
    tokens_array = []
    for line in ud.splitlines():
        tokens_array += split_escapes(line + "\n")
    return CfnSimpleExpr({ "Fn::Base64": {
            "Fn::Join": [
              "", tokens_array
            ]
          } })
