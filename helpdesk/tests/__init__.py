# import all test_*.py files in directory.
# neccessary for automatic discovery in django <= 1.5
# http://stackoverflow.com/a/15780326/1382740

import unittest


def suite():
    return unittest.TestLoader().discover("helpdesk.tests", pattern="test_*.py")
