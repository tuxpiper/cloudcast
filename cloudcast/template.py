'''
Symbols available to templates 

Created on Jun 13, 2013

@author: David Losada Carballo <david@tuxpiper.com>
'''

from cloudcast.elements import Parameter, Mapping, Resource, Output

class AWS:
    from cloudcast.elements import CfnSimpleExpr
    Region = CfnSimpleExpr({ "Ref" : "AWS::Region" })
    StackName = CfnSimpleExpr({ "Ref" : "AWS::StackName" })
    AZs = CfnSimpleExpr({ "Fn::GetAZs" : "" })

# Wrapper in order to generate JSON for AWS's "Fn::Join" built-in
def join(token, *kargs):
    from cloudcast.elements import CfnSimpleExpr
    return CfnSimpleExpr({ "Fn::Join" : [ token, list(kargs) ] })
