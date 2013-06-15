'''
Test/sample cloudcast template 

Created on Jun 13, 2013

@author: David Losada Carballo <david@tuxpiper.com>
'''

from cloudcast.template import *
from cloudcast.library import stack_user
from cloudcast import stack

stack.set_description("Simple CFN test")

keyName = "default"

PreciseAMIs = Mapping({
    "us-west-2" : { "ebs": "ami-6335a453", "instance": "ami-4933a279" }
})

# SQS queues example
SQSQueue1 = Resource("AWS::SQS::Queue")
SQSQueue2 = Resource("AWS::SQS::Queue")

AnInstance = Resource(
    "AWS::EC2::Instance",
    ImageId = PreciseAMIs.find(AWS.Region, "ebs"),
    InstanceType = "m1.small",
    KeyName = keyName,
    UserData = { "Fn::Base64" : { "Fn::Join" : ["", [
        '#!/bin/bash\n',
        'apt-get update\n'
        '[ ! -x /usr/bin/easy_install ] && apt-get install -y python-setuptools\n'
        '[ ! -x /usr/local/bin/pip ] && {\n',
        '  curl -o /tmp/get-pip.py -s https://raw.github.com/pypa/pip/master/contrib/get-pip.py; \n',
        '  python /tmp/get-pip.py ; }\n',
        '/usr/local/bin/pip install https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-1.3.14.tar.gz"\n',
        'cfn-init -s ', AWS.StackName,
                 " -r ",  Resource.this_resource_name,
                 " --access-key ", stack_user.CloudFormationStackUserKey,
                 " --secret-key ", stack_user.CloudFormationStackUserKey["SecretAccessKey"],
                 " --region ", AWS.Region, ' || { echo  "Fatal error during cfn-init" ; exit 1 ; }\n',
        '} 2>&1 | tee -a /bootstrap.log'
    ]]}},
    Metadata = {
        'AWS::CloudFormation::Init' : {
            "config" : {
                "packages": {
                    "apt" : {
                        "g++" : [],
                    }
                },
                "files" : {
                    "/etc/myqueues.json" : {
                        "content" : {
                            "Queue1": SQSQueue1['QueueName'],
                            "Queue2": SQSQueue2['QueueName']
                        },
                        "mode": "000644",
                        "owner": "root",
                        "group": "root"
                    }
                }
            }
        }
    }
)
    
    
