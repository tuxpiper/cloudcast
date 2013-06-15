'''
The stack module provides a singleton for the stack being processed.
This module is designed to be reloaded every time a new stack is
being processed

Created on Jun 13, 2013

@author: David Losada Carballo <david@tuxiper.com>
'''

description = None
required_capabilities = []

def add_required_capability(cap):
    global required_capabilites
    if cap not in required_capabilities:
        required_capabilities.append(cap)

def set_description(desc):
    global description
    description = desc
    
def get_description():
    global description
    return description