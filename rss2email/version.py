# Copyright (C) 2013 W. Trevor King <wking@tremily.us>
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

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
