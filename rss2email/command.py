# Copyright (C) 2012-2021 Etienne Millon <me@emillon.org>
#                         Gregory Soutade <gregory@soutade.fr>
#                         Kaashif Hymabaccus <kaashif@kaashif.co.uk>
#                         Karthikeyan Singaravelan <tir.karthi@gmail.com>
#                         Léo Gaspard <leo@gaspard.io>
#                         Martin Monperrus <monperrus@users.noreply.github.com>
#                         Nicolas KAROLAK <nicolas@karolak.fr>
#                         Profpatsch <mail@profpatsch.de>
#                         W. Trevor King <wking@tremily.us>
#                         auouymous <5005204+auouymous@users.noreply.github.com>
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

"""rss2email commands
"""

import os as _os
import re as _re
import sys as _sys
import xml.dom.minidom as _minidom
import xml.sax.saxutils as _saxutils
import urllib as _urllib
import time as _time

from . import LOG as _LOG
from . import error as _error

def new(feeds, args):
    "Create a new feed database."
    if args.email:
        _LOG.info('set the default target email to {}'.format(args.email))
        feeds.config['DEFAULT']['to'] = args.email
    if _os.path.exists(feeds.configfiles[-1]):
        raise _error.ConfigAlreadyExistsError(feeds=feeds)
    feeds.save()

def email(feeds, args):
    "Update the default target email address"
    if not args.email:
        _LOG.info('unset the default target email')
    else:
        _LOG.info('set the default target email to {}'.format(args.email))
    feeds.config['DEFAULT']['to'] = args.email
    feeds.save()

def add(feeds, args):
    "Add a new feed to the database"
    feed = feeds.new_feed(name=args.name, url=args.url, to=args.email)
    _LOG.info('add new feed {}'.format(feed))
    if not feed.to:
        raise _error.NoToEmailAddress(feed=feed, feeds=feeds)
    feeds.save()

def run(feeds, args):
    "Fetch feeds and send entry emails."
    if not args.index:
        args.index = range(len(feeds))
    try:
        # How long (in seconds) to sleep between running feeds with
        # the same server.
        interval = float(feeds.config['DEFAULT']['same-server-fetch-interval'])

        # We use the domain name to determine if we are fetching from
        # the same server twice in a row.
        last_server = "example.com"
        for index in args.index:
            feed = feeds.index(index)
            # to debug feeds that timeout, run "r2e -VV run"
            _LOG.info('refreshing feed {}'.format(feed))
            if feed.active:
                current_server = _urllib.parse.urlparse(feed.url).netloc
                try:
                    if last_server == current_server:
                        _LOG.info('fetching from server {current_server} again, sleeping for {interval}s'.format(
                            current_server = current_server,
                            interval = interval
                        ))
                        _time.sleep(interval)
                    feed.run(send=args.send, clean=args.clean)
                except _error.RSS2EmailError as e:
                    e.log()
                last_server = current_server
    finally:
        feeds.save()

def list(feeds, args):
    "List all the feeds in the database"
    for i,feed in enumerate(feeds):
        if feed.active:
            active_char = '*'
        else:
            active_char = ' '
        print('{}: [{}] {}'.format(i, active_char, feed))

def _set_active(feeds, args, active=True):
    "Shared by `pause` and `unpause`."
    if active:
        action = 'unpause'
    else:
        action = 'pause'
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('{} feed {}'.format(action, feed))
        feed.active = active
    feeds.save()

def pause(feeds, args):
    "Pause a feed (disable fetching)"
    _set_active(feeds=feeds, args=args, active=False)

def unpause(feeds, args):
    "Unpause a feed (enable fetching)"
    _set_active(feeds=feeds, args=args, active=True)

def delete(feeds, args):
    "Remove a feed from the database"
    to_remove = []
    for index in args.index:
        feed = feeds.index(index)
        to_remove.append(feed)
    for feed in to_remove:
        _LOG.info('deleting feed {}'.format(feed))
        feeds.remove(feed)
    feeds.save()

def reset(feeds, args):
    "Forget dynamic feed data (e.g. to re-send old entries)"
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('resetting feed {}'.format(feed))
        feed.reset()
    feeds.save()

def opmlimport(feeds, args):
    "Import configuration from OPML."
    if args.file:
        _LOG.info('importing feeds from {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        _LOG.info('importing feeds from stdin')
        f = _sys.stdin
    try:
        dom = _minidom.parse(f)
        new_feeds = dom.getElementsByTagName('outline')
    except Exception as e:
        raise _error.OPMLReadError() from e
    if args.file:
        f.close()
    name_slug_regexp = _re.compile(r'[^\w\d.-]+')
    for feed in new_feeds:
        if feed.hasAttribute('xmlUrl'):
            url = _saxutils.unescape(feed.getAttribute('xmlUrl'))
            name = None
            if feed.hasAttribute('text'):
                text = _saxutils.unescape(feed.getAttribute('text'))
                if text != url:
                    name = name_slug_regexp.sub('-', text)
            feed = feeds.new_feed(name=name, url=url)
            _LOG.info('add new feed {}'.format(feed))
    feeds.save()

def opmlexport(feeds, args):
    "Export configuration to OPML."
    if args.file:
        _LOG.info('exporting feeds to {}'.format(args.file))
        f = open(args.file, 'wb')
    else:
        _LOG.info('exporting feeds to stdout')
        f = _sys.stdout.buffer
    f.write(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<opml version="1.0">\n'
        b'<head>\n'
        b'<title>rss2email OPML export</title>\n'
        b'</head>\n'
        b'<body>\n')
    for feed in feeds:
        if not feed.url:
            _LOG.debug('dropping {}'.format(feed))
            continue
        name = _saxutils.escape(feed.name)
        url = _saxutils.escape(feed.url)
        f.write('<outline type="rss" text="{}" xmlUrl="{}"/>\n'.format(
                name, url).encode())
    f.write(
        b'</body>\n'
        b'</opml>\n')
    if args.file:
        f.close()
