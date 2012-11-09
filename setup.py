"A python script that converts RSS/Atom newsfeeds to email"

import codecs as _codecs
from distutils.core import setup
import os.path as _os_path

from rss2email import __version__


_this_dir = _os_path.dirname(__file__)

setup(
    name='rss2email',
    version=__version__,
    maintainer='W. Trevor King',
    maintainer_email='wking@tremily.us',
    url='http://pypi.python.org/pypi/rss2email/',
    download_url='http://git.tremily.us/?p=rss2email.git;a=snapshot;h=v{};sf=tgz'.format( __version__),
    license='GNU General Public License (GPL)',
    platforms=['all'],
    description=__doc__,
    long_description=_codecs.open(
        _os_path.join(_this_dir, 'README'), 'r', encoding='utf-8').read(),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Topic :: Communications :: Email',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    py_modules=['rss2email'],
    scripts=['r2e'],
    provides=['rss2email'],
    )
