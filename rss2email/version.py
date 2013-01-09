# Copyright

"""Calculate version numbers for this package and its dependencies

This makes it easier for users to submit useful bug reports.
"""

import importlib as _importlib
import sys as _sys

from . import __version__


def get_rss2email_version(package):
    return __version__

def get_python_version(package):
    return _sys.version

def get_python_package_version(package):
    try:
        module = _importlib.import_module(package)
    except ImportError as e:
        return None
    return getattr(module, '__version__', 'unknown')

def get_versions(packages=None):
    if not packages:
        packages = ['rss2email', 'python', 'feedparser', 'html2text']
    for package in packages:
        get = globals().get(
            'get_{}_version'.format(package),
            get_python_package_version)
        version = get(package=package)
        yield (package, version)
