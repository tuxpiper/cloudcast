'''
Symbols available to templates. Just

  from cloudcast.template import *

and use at your heart's content!

@author: David Losada Carballo <david@tuxpiper.com>
'''

from cloudcast.elements import \
	Parameter, Mapping, Resource, Output, EC2Instance, EC2LaunchConfiguration, \
	WaitCondition, WaitConditionHandle, get_ref_name

class AWS:
    from cloudcast.elements import CfnSimpleExpr, CfnRegionExpr
    Region = CfnRegionExpr()
    StackName = CfnSimpleExpr({ "Ref" : "AWS::StackName" })
    AZs = CfnSimpleExpr({ "Fn::GetAZs" : "" })

# Wrapper in order to generate JSON for AWS's "Fn::Join" built-in
def join(token, *kargs):
    from cloudcast.elements import CfnSimpleExpr
    return CfnSimpleExpr({ "Fn::Join" : [ token, list(kargs) ] })

# Wrapper around Fn::Select cfn function
def select(listOfObjects, index):
    from cloudcast.elements import CfnSelectExpr
    return CfnSelectExpr(listOfObjects, index)
