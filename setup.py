'''
Created on Jun 14, 2013

@author: David Losada Carballo <david@tuxpiper.com>
'''

from setuptools import setup, find_packages

setup(
    name = "cloudcast",
    description = ("Easy and powerful stack templates for AWS CloudFormation"),
    author = "David Losada Carballo",
    author_email = "david@tuxpiper.com",
    version = "0.0.1",
    packages = find_packages(),
    license = 'MIT',
    keywords = "aws internet cloud cloudformation deployment automation",
    long_description = open('README.md').read(),
    url = "http://github.com/tuxpiper/cloudcast",
    zip_safe = True,
    classifiers=[
       "Development Status :: 1 - Planning",
       "Topic :: System",
       "Environment :: Console",
       "Intended Audience :: System Administrators",
       "License :: OSI Approved :: MIT License",
       "Programming Language :: Python"
    ],
    
    # We may use boto later, for interacting with AWS services, but not yet
    #install_requires = [ 'boto>=2.7.0' ]    
)
