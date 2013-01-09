# Copyright (C) 2012-2013 W. Trevor King <wking@tremily.us>
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

"""rss2email: get RSS feeds emailed to you
"""

import logging as _logging
import sys as _sys


__version__ = '2.71'
__url__ = 'http://rss2email.infogami.com'
__author__ = 'W. Trevor King'
__copyright__ = '(C) 2004 Aaron Swartz. GNU GPL 2 or 3.'
__contributors__ = [
    'Dean Jackson',
    'Brian Lalor',
    'Joey Hess',
    'Matej Cepl',
    "Martin 'Joey' Schulze",
    'Marcel Ackermann (http://www.DreamFlasher.de)',
    'Lindsey Smith (lindsey@allthingsrss.com)',
    'Erik Hetzner',
    'W. Trevor King',
    'Aaron Swartz (original author)',
    ]

LOG = _logging.getLogger('rss2email')
LOG.addHandler(_logging.StreamHandler())
LOG.setLevel(_logging.ERROR)


if _sys.version_info < (3, 2):
    raise ImportError(
        "rss2email requires Python 3.2, but you're using:\n{}".format(
            _sys.version))
