'''
Test/sample cloudcast template 

@author: David Losada Carballo <david@tuxpiper.com>
'''

from cloudcast.template import *
from cloudcast.library import stack_user
from _context import stack

from cloudcast.iscm.ansible import AnsibleISCM

keyName = "david"

TrustyAMIs = Mapping({
    "us-east-1" : { "ebs": "ami-64e27e0c", "ebsssd": "ami-74e27e1c" },
    "us-west-2" : { "ebs": "ami-978dd9a7", "ebsssd": "ami-818dd9b1" }
})

SQSQueue1 = Resource("AWS::SQS::Queue")
SQSQueue2 = Resource("AWS::SQS::Queue")

AnInstance = EC2Instance(
    ImageId = TrustyAMIs.find(AWS.Region, "ebs"),
    InstanceType = stack.env['instance_type'],
    KeyName = keyName,
    iscm = AnsibleISCM(
        config= dict(
            inst_home= "/home/ubuntu",
            inst_user= "ubuntu",
            inst_group= "ubuntu",
            inst_playbook_dir= "playbooks"
            ),
        facts= dict(
            queue1_name= SQSQueue1['QueueName'],
            queue2_name= SQSQueue2['QueueName'],
            environment= "production"
            ),
        playbooks_source= "ansible",
        stack_user_key= stack_user.CloudFormationStackUserKey,
        runs= dict(
            build= dict(
                playbook= "playbook.yaml",
                sudo= True,
                tags= [ "build" ],
                ),
            boot= dict(
                playbook= "playbook.yaml",
                extra_vars= dict(
                    somevar= "value"
                    ),
                sudo= True,
                tags= [ "boot" ],
                )
            )
        )
    )
    
    
