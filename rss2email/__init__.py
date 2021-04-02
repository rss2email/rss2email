# Copyright (C) 2012-2021 Adam Mokhtari <2553423+uutari@users.noreply.github.com>
#                         Andrey Zelenchuk <azelenchuk@plesk.com>
#                         François Boulogne <fboulogne sciunto org>
#                         Léo Gaspard <leo@gaspard.io>
#                         Profpatsch <mail@profpatsch.de>
#                         W. Trevor King <wking@tremily.us>
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


__version__ = '3.13'
__url__ = 'https://github.com/rss2email/rss2email'
__author__ = 'The rss2email maintainers'
__email__ = 'rss2email@tremily.us'
__copyright__ = '(C) 2004 Aaron Swartz. GNU GPL 2 or 3.'

LOG = _logging.getLogger('rss2email')
LOG.addHandler(_logging.StreamHandler())
LOG.setLevel(_logging.ERROR)


min_python_version = (3, 5)
if _sys.version_info < min_python_version:
    raise ImportError(
        "rss2email requires Python {maj}.{min} or newer, but you're using:\n{got}"
        .format(
            maj=min_python_version[0],
            min=min_python_version[1],
            got=_sys.version
        ))
