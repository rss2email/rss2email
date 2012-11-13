# Copyright

"""rss2email commands
"""

import sys as _sys
import xml.dom.minidom as _minidom
import xml.sax.saxutils as _saxutils

from . import LOG as _LOG
from . import error as _error


def new(feeds, args):
    "Create a new feed database."
    if args.email:
        _LOG.info('set the default target email to {}'.format(args.email))
        feeds.config['DEFAULT']['to'] = args.email
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
        raise _error.NoToEmailAddress(feeds=feeds)
    feeds.save()

def run(feeds, args):
    "Fetch feeds and send entry emails."
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        if feed.active:
            try:
                feed.run(send=args.send)
            except _error.NoToEmailAddress as e:
                e.log()
            except _error.ProcessingError as e:
                e.log()
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
    for feed in new_feeds:
        if feed.hasAttribute('xmlUrl'):
            url = _saxutils.unescape(feed.getAttribute('xmlUrl'))
            feed = feeds.new_feed(url=url)
            _LOG.info('add new feed {}'.format(feed))
    feeds.save()

def opmlexport(feeds, args):
    "Export configuration to OPML."
    if args.file:
        _LOG.info('exporting feeds to {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        _LOG.info('exporting feeds to stdout')
        f = _sys.stdout
    f.write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="1.0">\n'
        '<head>\n'
        '<title>rss2email OPML export</title>\n'
        '</head>\n'
        '<body>\n')
    for feed in feeds:
        url = _saxutils.escape(feed.url)
        f.write('<outline type="rss" text="{0}" xmlUrl="{0}"/>'.format(url))
    f.write(
        '</body>\n'
        '</opml>\n')
    if args.file:
        f.close()
