'''
Template module that provides an user with privileges to read the CloudFormation
stack definition. You usually want such an user when doing advanced operations
with Metadata (i.e. using the cfn-init utils)

@author: David Losada Carballo <david@tuxpiper.com>
'''

from _context import stack
from cloudcast.template import *

stack.add_required_capability("CAPABILITY_IAM")

CloudformationStackUser = Resource(
        "AWS::IAM::User",
        Path="/stackusers/",
        Policies=[{
            "PolicyName": "cfn_user_access",
            "PolicyDocument": {
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "cloudformation:DescribeStackResource",
                    "Resource":"*"
                }]
            }
        }]
    )

CloudFormationStackUserKey = Resource(
        "AWS::IAM::AccessKey",
        Status="Active",
        UserName=CloudformationStackUser
)
