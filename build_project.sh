#!/bin/sh
# django-helpdesk shell script to upload to pypi.

WORKDIR=/tmp/django-helpdesk-build.$$
mkdir $WORKDIR
pushd $WORKDIR

git clone git://github.com/rossp/django-helpdesk.git
cd django-helpdesk

/usr/bin/python2.4 setup.py bdist_egg upload
/usr/bin/python2.5 setup.py bdist_egg upload
/usr/bin/python2.5 setup.py sdist upload

popd
rm -rf $WORKDIR
