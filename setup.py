# Copyright (C) 2012-2021 Adam Mokhtari <2553423+uutari@users.noreply.github.com>
#                         Andrey Zelenchuk <azelenchuk@plesk.com>
#                         Arun Persaud <apersaud@lbl.gov>
#                         Léo Gaspard <leo@gaspard.io>
#                         Markus Unterwaditzer <markus@unterwaditzer.net>
#                         Profpatsch <mail@profpatsch.de>
#                         Steven Siloti <ssiloti@gmail.com>
#                         W. Trevor King <wking@tremily.us>
#                         auouymous <5005204+auouymous@users.noreply.github.com>
#                         auouymous <au@qzx.com>
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

"A python script that converts RSS/Atom newsfeeds to email"

import codecs as _codecs
import os.path as _os_path
import setuptools

from rss2email import __version__, __url__, __author__, __email__


_this_dir = _os_path.dirname(__file__)

setuptools.setup(
    name='rss2email',
    version=__version__,
    maintainer=__author__,
    maintainer_email=__email__,
    url=__url__,
    download_url='{}/archive/v{}.tar.gz'.format(__url__, __version__),
    license='GNU General Public License (GPL)',
    platforms=['all'],
    description=__doc__,
    long_description=_codecs.open(
        _os_path.join(_this_dir, 'README.rst'), 'r', encoding='utf-8').read(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Communications :: Email',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    packages=['rss2email', 'rss2email.post_process'],
    scripts=['r2e'],
    provides=['rss2email'],
    install_requires=[
        'feedparser>=6.0.0',
        'html2text>=2020.1.16',
        ],
    )
