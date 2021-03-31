# Copyright (C) 2012-2021 Andrey Zelenchuk <azelenchuk@parallels.com>
#                         Andrey Zelenchuk <azelenchuk@plesk.com>
#                         Gregory Soutade <gregory@soutade.fr>
#                         Kaashif Hymabaccus <kaashif@kaashif.co.uk>
#                         Lucas <lucas@sexy.is>
#                         Léo Gaspard <leo@gaspard.io>
#                         Profpatsch <mail@profpatsch.de>
#                         W. Trevor King <wking@tremily.us>
#                         auouymous <5005204+auouymous@users.noreply.github.com>
#                         ryneeverett <ryneeverett@gmail.com>
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

"""Define the rss2email command line interface
"""

import argparse as _argparse
import logging as _logging
import sys as _sys
import os as _os

from . import __doc__ as _PACKAGE_DOCSTRING
from . import __version__
from . import LOG as _LOG
from . import command as _command
from . import error as _error
from . import feeds as _feeds
from . import version as _version
from .feeds import UNIX


class FullVersionAction (_argparse.Action):
    def __call__(self, *args, **kwargs):
        for package,version in _version.get_versions():
            print('{} {}'.format(package, version))
        _sys.exit(0)


def run(*args, **kwargs):
    """The rss2email command line interface

    Arguments passed to this function are forwarded to the parser's
    `.parse_args()` call without modification.
    """
    parser = _argparse.ArgumentParser(
        prog='rss2email', description=_PACKAGE_DOCSTRING)

    parser.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s {}'.format(__version__))
    parser.add_argument(
        '--full-version', action=FullVersionAction, nargs=0,
        help='print the version information of all related packages and exit')
    parser.add_argument(
        '-c', '--config', metavar='PATH', default=[], action='append',
        help='path to the configuration file')
    parser.add_argument(
        '-d', '--data', metavar='PATH',
        help='path to the feed data file')
    parser.add_argument(
        '-V', '--verbose', default=0, action='count',
        help='increment verbosity')
    subparsers = parser.add_subparsers(title='commands')

    new_parser = subparsers.add_parser(
        'new', help=_command.new.__doc__.splitlines()[0])
    new_parser.set_defaults(func=_command.new)
    new_parser.add_argument(
        'email', nargs='?',
        help='default target email for the new feed database')

    email_parser = subparsers.add_parser(
        'email', help=_command.email.__doc__.splitlines()[0])
    email_parser.set_defaults(func=_command.email)
    email_parser.add_argument(
        'email', default='',
        help='default target email for the email feed database')

    add_parser = subparsers.add_parser(
        'add', help=_command.add.__doc__.splitlines()[0])
    add_parser.set_defaults(func=_command.add)
    add_parser.add_argument(
        'name', help='name of the new feed')
    add_parser.add_argument(
        'url', help='location of the new feed')
    add_parser.add_argument(
        'email', nargs='?',
        help='target email for the new feed')

    run_parser = subparsers.add_parser(
        'run', help=_command.run.__doc__.splitlines()[0])
    run_parser.set_defaults(func=_command.run)
    run_parser.add_argument(
        '-n', '--no-send', dest='send',
        default=True, action='store_const', const=False,
        help="fetch feeds, but don't send email")
    run_parser.add_argument(
        '--clean', action='store_true',
        help='clean old feed entries')
    run_parser.add_argument(
        'index', nargs='*',
        help='feeds to fetch (defaults to fetching all feeds)')

    list_parser = subparsers.add_parser(
        'list', help=_command.list.__doc__.splitlines()[0])
    list_parser.set_defaults(func=_command.list)

    pause_parser = subparsers.add_parser(
        'pause', help=_command.pause.__doc__.splitlines()[0])
    pause_parser.set_defaults(func=_command.pause)
    pause_parser.add_argument(
        'index', nargs='*',
        help='feeds to pause (defaults to pausing all feeds)')

    unpause_parser = subparsers.add_parser(
        'unpause', help=_command.unpause.__doc__.splitlines()[0])
    unpause_parser.set_defaults(func=_command.unpause)
    unpause_parser.add_argument(
        'index', nargs='*',
        help='feeds to ununpause (defaults to unpausing all feeds)')

    delete_parser = subparsers.add_parser(
        'delete', help=_command.delete.__doc__.splitlines()[0])
    delete_parser.set_defaults(func=_command.delete)
    delete_parser.add_argument(
        'index', nargs='+',
        help='feeds to delete')

    reset_parser = subparsers.add_parser(
        'reset', help=_command.reset.__doc__.splitlines()[0])
    reset_parser.set_defaults(func=_command.reset)
    reset_parser.add_argument(
        'index', nargs='*',
        help='feeds to reset (defaults to resetting all feeds)')

    opmlimport_parser = subparsers.add_parser(
        'opmlimport', help=_command.opmlimport.__doc__.splitlines()[0])
    opmlimport_parser.set_defaults(func=_command.opmlimport)
    opmlimport_parser.add_argument(
        'file', metavar='PATH', nargs='?',
        help='path for imported OPML (defaults to stdin)')

    opmlexport_parser = subparsers.add_parser(
        'opmlexport', help=_command.opmlexport.__doc__.splitlines()[0])
    opmlexport_parser.set_defaults(func=_command.opmlexport)
    opmlexport_parser.add_argument(
        'file', metavar='PATH', nargs='?',
        help='path for exported OPML (defaults to stdout)')

    args = parser.parse_args(*args, **kwargs)

    if args.verbose:
        _LOG.setLevel(max(_logging.DEBUG, _logging.ERROR - 10 * args.verbose))

    # https://docs.python.org/3/library/logging.html#logrecord-attributes
    formatter = _logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    for handler in _LOG.handlers: # type: _logging.Handler
        handler.setFormatter(formatter)

    if not getattr(args, 'func', None):
        parser.error('too few arguments')

    # Immediately lock so only one r2e instance runs at a time
    if UNIX:
        import fcntl as _fcntl
        from pathlib import Path as _Path
        dir = _os.environ.get("XDG_RUNTIME_DIR")
        if dir is None:
            dir = _os.path.join("/tmp", "rss2email-{}".format(_os.getuid()))
            _Path(dir).mkdir(mode=0o700, parents=True, exist_ok=True)
        lockfile_path = _os.path.join(dir, "rss2email.lock")
        lockfile = open(lockfile_path, "w")
        _fcntl.lockf(lockfile, _fcntl.LOCK_EX)
        _LOG.debug("acquired lock file {}".format(lockfile_path))
    else:
        # TODO: What to do on Windows?
        lockfile = None

    try:
        if not args.config:
            args.config = None
        feeds = _feeds.Feeds(datafile_path=args.data, configfiles=args.config)
        if args.func != _command.new:
            feeds.load()
        if not args.verbose:
            _LOG.setLevel(feeds.config['DEFAULT']['verbose'].upper())
        args.func(feeds=feeds, args=args)
    except _error.RSS2EmailError as e:
        e.log()
        if _logging.ERROR - 10 * args.verbose < _logging.DEBUG:
            raise  # don't mask the traceback
        _sys.exit(1)
    finally:
        if lockfile is not None:
            lockfile.close()


if __name__ == '__main__':
    run()
