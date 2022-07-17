# -*- coding: utf-8 -*-
"""Python packaging."""

from __future__ import unicode_literals

from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(here)


NAME = 'django-helpdesk-demodesk'
DESCRIPTION = 'A demo Django project using django-helpdesk'
README = open(os.path.join(here, 'README.rst')).read()
VERSION = '0.4.1'
#VERSION = open(os.path.join(project_root, 'VERSION')).read().strip()
AUTHOR = 'django-helpdesk team'
URL = 'https://github.com/django-helpdesk/django-helpdesk'
CLASSIFIERS = ['Development Status :: 4 - Beta',
               'License :: OSI Approved :: BSD License',
               'Programming Language :: Python :: 3.8',
               'Programming Language :: Python :: 3.9',
               'Programming Language :: Python :: 3.10',
               'Framework :: Django :: 3.2',
               'Framework :: Django :: 4.0']
KEYWORDS = []
PACKAGES = ['demodesk']
REQUIREMENTS = [
    'django-helpdesk'
]
ENTRY_POINTS = {
    'console_scripts': ['demodesk = demodesk.manage:main']
}


if __name__ == '__main__':  # Don't run setup() when we import this module.
    setup(name=NAME,
          version=VERSION,
          description=DESCRIPTION,
          long_description=README,
          classifiers=CLASSIFIERS,
          keywords=' '.join(KEYWORDS),
          author=AUTHOR,
          url=URL,
          license='BSD',
          packages=PACKAGES,
          include_package_data=True,
          zip_safe=False,
          install_requires=REQUIREMENTS,
          entry_points=ENTRY_POINTS)
