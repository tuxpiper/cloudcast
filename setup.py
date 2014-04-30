'''
@author: David Losada Carballo <david@tuxpiper.com>
'''

from setuptools import setup, find_packages

setup(
    name = "cloudcast",
    version = "0.0.8",
    packages = find_packages(),
    package_data = {
        # Script files that contain initial bootstrap sequences
        'cloudcast.iscm': ['scripts/*']
    },
    install_requires = ['dq>=0.1.2'],

    description = ("Easy and powerful stack templates for AWS CloudFormation"),
    author = "David Losada Carballo",
    author_email = "david@tuxpiper.com",
    license = 'MIT',
    keywords = "aws internet cloud cloudformation deployment automation",
    long_description = open('README.md').read(),
    url = "http://github.com/tuxpiper/cloudcast",
    zip_safe = False,
    classifiers=[
       "Development Status :: 2 - Pre-Alpha",
       "Topic :: System",
       "Environment :: Console",
       "Intended Audience :: System Administrators",
       "License :: OSI Approved :: MIT License",
       "Programming Language :: Python"
    ], 
)
