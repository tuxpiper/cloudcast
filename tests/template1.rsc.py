'''
Test/sample cloudcast template 

@author: David Losada Carballo <david@tuxpiper.com>
'''

from cloudcast.template import *
from cloudcast.library import stack_user
from _context import stack

from cloudcast.iscm.cfninit import CfnInit

keyName = "ec2deploy"

PreciseAMIs = Mapping({
    "us-east-1" : { "ebs": "ami-0b9c9f62", "instance": "ami-6f969506" },
    "us-west-2" : { "ebs": "ami-6335a453", "instance": "ami-4933a279" }
})

# SQS queues example
SQSQueue1 = Resource("AWS::SQS::Queue")
SQSQueue2 = Resource("AWS::SQS::Queue")

AnInstance = EC2Instance(
    ImageId = PreciseAMIs.find(AWS.Region, "ebs"),
    InstanceType = stack.env['instance_type'],
    KeyName = keyName,
    iscm = [
        CfnInit(
            stack_user_key=stack_user.CloudFormationStackUserKey,
            configs=[
                {
                    "commands" : {
                        "apt-update" : {
                            "command" : "apt-get update"
                        }
                    }
                },
                {
                    "packages": {
                        "apt": { "git": [] }
                    },
                    "files": {
                        "/etc/myqueues.json": {
                            "content" : {
                                "Queue1": SQSQueue1['QueueName'],
                                "Queue2": SQSQueue2['QueueName']
                            },
                            "mode": "000644",
                            "owner": "root",
                            "group": "root"
                        }
                    }
                },
                {
                    "users": {
                        "awsuser": {
                            "uid": "1001",
                            "homeDir" : "/home/user"
                        }
                    }
                }
            ],
        )
    ]
)
    
    
