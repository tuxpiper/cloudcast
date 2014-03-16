CloudCast - Easy and powerful stack templates for AWS CloudFormation
====================================================================

What is it?
-----------

AWS CloudFormation is pretty powerful, but once your stacks are getting
sophisticated, it can be hard to work with. You may easily get
lost in a sea of maps and lists, and it can be hard to keep track of
references across your resources.

Also, this may be my personal pet peeve, but JSON has no syntax for comments!
This makes templates written for CFN hard to document and maintain.

With CloudCast you can easily create any template you would write for CFN, but
using plain Python syntax.

Resources, Mappings, Parameters and Outputs are defined as Python objects. It
looks cleaner and you can do smarter stuff with them!

For instance:

    from cloudcast.template import Resource

	LoadBalancer = Resource(
	    "AWS::ElasticLoadBalancing::LoadBalancer",
	    AvailabilityZones=[ 'us-east-1c', 'us-east-1d' ],
	    HealthCheck={
	        "HealthyThreshold" : "2",
	        "Interval" : "30",
	        "Target" : "HTTP:80/status",
	        "Timeout" : "5",
	        "UnhealthyThreshold" : "3"
	    },
	    Listeners=[{
	        "InstancePort" : "80",
	        "InstanceProtocol" : 'HTTP',
	        "LoadBalancerPort" : "80",
	        "Protocol" : 'HTTP',
	    }]
	    ),
	)
	
If you are familiar with AWS and CFN, this structure shouldn't be strange to you.
We have just declared an ELB resource with some properties.

Later on, the load balancer may be referenced from a security group, in order to
be allowed to access the service ports in the balanced instances:

	AppSG = Resource(
	    "AWS::EC2::SecurityGroup",
	    GroupDescription = "Allow access app from LB only",
	    SecurityGroupIngress = [ {
	        "IpProtocol" : "tcp",
	        "FromPort" : 80,
	        "ToPort" : 80,
	        "SourceSecurityGroupOwnerId" : LoadBalancer['SourceSecurityGroup.OwnerAlias'],
	        "SourceSecurityGroupName": LoadBalancer['SourceSecurityGroup.GroupName'],
	    }]
	)

Since you are dealing with Python objects, nothing is stopping you from
bundling them in your own libraries and reusing them as necessary. We have
an example of that around here (look at the cloudcast.library.stack_user module).

In fact, you can create any Python code that may help you making your
templates simpler and more expressive!

How do you get the JSON templates?
----------------------------------

Once you've got your template python file (let's call it template.py), you would:

	from cloudcast import Stack
	stack = Stack(
		description = "Sample stack that doesn't do much",
		env = { ... define environment vars here ... },
		resources_file = "template.py"
	)
	print stack.dump_json()

The following will happen:

1. The Stack class will load, examine your code module and find
the relevant objects to be included in the CloudFormation template (resources,
outputs, parameters..). It shouldn't get confused with any other code you
may have there.
2. The template will be printed out for you to feed into CloudFormation.

Special thanks
--------------

[Bright & Shiny](http://brightandshiny.com/) - their support and fine
understanding of well managed infrastructure, made it possible for me to
devote the necessary efforts to evolve this concept.

If you are looking for an awesome software agency make sure to check their
website!

[Lifestreams Technology](http://lifestreams.com/) - developing for their
products has proved to be an excellent ground to develop and put into
practice new ideas such as the one that originated this project. Thanks
for the chance to bring CloudCast to the point where it is a key technology
to support mission-critical operations.
