from cloudcast import Stack

stack1 = Stack(
	description = "Sample stack that doesn't do much",
	env = {
		"instance_type": "c3.large"
	},
	resources_file = "template1.rsc.py"
)

print stack1.dump_json()
