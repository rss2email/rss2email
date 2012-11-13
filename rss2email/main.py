"""Define the rss2email command line interface
"""

import argparse as _argparse
import sys as _sys

from . import __doc__ as _PACKAGE_DOCSTRING
from . import __version__
from . import command as _command
from . import error as _error
from . import feeds as _feeds


def run(*args, **kwargs):
    """The rss2email command line interface

    Arguments passed to this function are forwarded to the parser's
    `.parse_args()` call without modification.
    """
    parser = _argparse.ArgumentParser(
        description=_PACKAGE_DOCSTRING, version=__version__)

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
        LOG.setLevel(max(_logging.DEBUG, _logging.ERROR - 10 * args.verbose))

    try:
        if not args.config:
            args.config = None
        feeds = _feeds.Feeds(datafile=args.data, configfiles=args.config)
        if args.func != _command.new:
            lock = args.func not in [_command.list, _command.opmlexport]
            feeds.load(lock=lock)
        args.func(feeds=feeds, args=args)
    except _error.RSS2EmailError as e:
        e.log()
        _sys.exit(1)


if __name__ == '__main__':
    run()
