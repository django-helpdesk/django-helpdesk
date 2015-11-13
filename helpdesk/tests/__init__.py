from os.path import dirname, basename, isfile
import glob

# import all test_*.py files in directory
modules = glob.glob(dirname(__file__)+"/test_*.py")
__all__ = [basename(f)[:-3] for f in modules if isfile(f)]
