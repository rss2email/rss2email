# Copyright

"""rss2email: get RSS feeds emailed to you
"""

import logging as _logging


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
