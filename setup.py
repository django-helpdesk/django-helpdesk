from setuptools import setup, find_packages
import os

version = '0.1.2'

LONG_DESCRIPTION = """
===============
django-helpdesk
===============

This is a Django-powered helpdesk ticket tracker, designed to
plug into an existing Django website and provide you with 
internal (or, perhaps, external) helpdesk management.
"""

setup(
    name='django-helpdesk',
    version=version,
    description="Django-powered ticket tracker for your helpdesk",
    long_description=LONG_DESCRIPTION,
    classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: Django",
        "Environment :: Web Environment",
        "Operating System :: OS Independent",
        "Intended Audience :: Customer Service",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Topic :: Office/Business",
        "Topic :: Software Development :: Bug Tracking",
    ],
    keywords=['django', 'helpdesk', 'tickets', 'incidents', 'cases'],
    author='Ross Poulton',
    author_email='ross@rossp.org',
    url='http://github.com/rossp/django-helpdesk',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=['setuptools'],
)

