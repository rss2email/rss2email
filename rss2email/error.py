# Copyright (C) 2012-2021 Etienne Millon <me@emillon.org>
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

"""rss2email-specific errors
"""

import sys as _sys

from . import LOG as _LOG
from . import __version__, __url__, __email__

import pprint as _pprint

import feedparser as _feedparser
import html2text as _html2text


class RSS2EmailError (Exception):
    def __init__(self, message):
        super(RSS2EmailError, self).__init__(message)

    def log(self):
        _LOG.error(str(self))
        if self.__cause__ is not None:
            _LOG.error('cause: {}'.format(self.__cause__))


class TimeoutError (RSS2EmailError):
    def __init__(self, time_limited_function):
        if time_limited_function.error is not None:
            message = (
                'error while running time limited function in {}: {}'.format(
                    time_limited_function.name, time_limited_function.error[1]))
        else:
            message = '{} second timeout exceeded in {}'.format(
                time_limited_function.timeout, time_limited_function.name)
        super(TimeoutError, self).__init__(message=message)
        self.time_limited_function = time_limited_function


class NoValidEncodingError (RSS2EmailError, ValueError):
    def __init__(self, string, encodings):
        message = 'no valid encoding for {} in {}'.format(string, encodings)
        super(NoValidEncodingError, self).__init__(message=message)
        self.string = string
        self.encodings = encodings


class SMTPConnectionError (RSS2EmailError, ValueError):
    def __init__(self, server, message=None):
        if message is None:
            message = 'could not connect to mail server {}'.format(server)
        super(SMTPConnectionError, self).__init__(message=message)
        self.server = server

    def log(self):
        super(SMTPConnectionError, self).log()
        _LOG.warning(
            'check your config file to confirm that smtp-server and other '
            'mail server settings are configured properly')
        if hasattr(self.__cause__, 'reason'):
            _LOG.error('reason: {}'.format(self.__cause__.reason))


class SMTPAuthenticationError (SMTPConnectionError):
    def __init__(self, server, username):
        message = (
            'could not authenticate with mail server {} as user {}'.format(
                server, username))
        super(SMTPAuthenticationError, self).__init__(
            server=server, message=message)
        self.username = username


class IMAPConnectionError (ValueError, RSS2EmailError):
    def __init__(self, server, port, message=None):
        if message is None:
            message = 'could not connect to mail server {}:{}'.format(
                server, port)
        super(IMAPConnectionError, self).__init__(message=message)
        self.server = server
        self.port = port

    def log(self):
        super(IMAPConnectionError, self).log()
        _LOG.warning(
            'check your config file to confirm that imap-server and other '
            'mail server settings are configured properly')
        if hasattr(self.__cause__, 'reason'):
            _LOG.error('reason: {}'.format(self.__cause__.reason))


class IMAPAuthenticationError (IMAPConnectionError):
    def __init__(self, server, port, username):
        message = (
            'could not authenticate with mail server {}:{} as user {}'.format(
                server, port, username))
        super(IMAPAuthenticationError, self).__init__(
            server=server, port=port, message=message)
        self.username = username


class SendmailError (RSS2EmailError):
    def __init__(self, status=None):
        if status:
            message = 'sendmail exited with code {}'.format(status)
        else:
            message = ''
        super(SendmailError, self).__init__(message=message)

    def log(self):
        super(SendmailError, self).log()
        _LOG.warning((
                'Error attempting to send email via sendmail. You may need '
                'to configure rss2email to use an SMTP server. Please refer '
                'to the rss2email documentation or website ({}) for complete '
                'documentation.').format(__url__))


class FeedError (RSS2EmailError):
    def __init__(self, feed, message=None, **kwargs):
        if message is None:
            message = 'error with feed {}'.format(feed.name)
        super(FeedError, self).__init__(message=message, **kwargs)
        self.feed = feed


class InvalidFeedConfig (FeedError):
    def __init__(self, setting, feed, message=None, **kwargs):
        if not message:
            message = (
                "invalid feed configuration '{setting}' in {feed}".format(
                    setting=getattr(feed, setting), feed=feed))
        super(InvalidFeedConfig, self).__init__(
            feed=feed, message=message, **kwargs)
        self.setting = setting


class InvalidFeedName (InvalidFeedConfig):
    def __init__(self, name, message=None, **kwargs):
        if not message:
            message = 'invalid feed name {!r}'.format(name)
        super(InvalidFeedName, self).__init__(
            setting='name', message=message, **kwargs)


class DuplicateFeedName (InvalidFeedName):
    def __init__(self, name, **kwargs):
        message = 'duplicate feed name {!r}'.format(name)
        super(DuplicateFeedName, self).__init__(
            name=name, message=message, **kwargs)


class ProcessingError (FeedError):
    def __init__(self, parsed, feed, message=None, **kwargs):
        if message is None:
            message = 'error processing feed {}'.format(feed)
        super(ProcessingError, self).__init__(feed=feed, message=message)
        self.parsed = parsed

    def log(self):
        super(ProcessingError, self).log()
        if type(self) == ProcessingError:  # not a more specific subclass
            _LOG.warning(
                '=== rss2email encountered a problem with this feed ===')
            _LOG.warning(
                '=== See the rss2email FAQ at {} for assistance ==='.format(
                    __url__))
            _LOG.warning(
                '=== If this occurs repeatedly, send this to {} ==='.format(
                    __email__))
            _LOG.warning(
                'error: {} {}'.format(
                    self.parsed.get('bozo_exception', "can't process"),
                    self.feed.url))
            _LOG.warning(_pprint.pformat(self.parsed))
            _LOG.warning('rss2email {}'.format(__version__))
            _LOG.warning('feedparser {}'.format(_feedparser.__version__))
            _LOG.warning('html2text {}'.format(_html2text.__version__))
            _LOG.warning('Python {}'.format(_sys.version))
            _LOG.warning('=== END HERE ===')


class HTTPError (FeedError):
    def __init__(self, status, feed, **kwargs):
        message = 'HTTP status {} fetching feed {}'.format(status, feed)
        super(HTTPError, self).__init__(feed=feed, message=message)
        self.status = status


class FeedsError (RSS2EmailError):
    def __init__(self, feeds=None, message=None, **kwargs):
        if message is None:
            message = 'error with feeds'
        super(FeedsError, self).__init__(message=message, **kwargs)
        self.feeds = feeds


class DataFileError (FeedsError):
    def __init__(self, feeds, message=None):
        if message is None:
            message = 'problem with the feed data file {}'.format(
                feeds.datafile)
        super(DataFileError, self).__init__(feeds=feeds, message=message)


class NoDataFile (DataFileError):
    def __init__(self, feeds):
        message = 'feed data file {} does not exist'.format(feeds.datafile)
        super(NoDataFile, self).__init__(feeds=feeds, message=message)

    def log(self):
        super(NoDataFile, self).log()
        _LOG.warning(
            "if you're using r2e for the first time, you have to run "
            "'r2e new' first.")


class NoToEmailAddress (InvalidFeedConfig, FeedsError):
    def __init__(self, feed, **kwargs):
        message = 'no target email address has been defined'
        super(NoToEmailAddress, self).__init__(
            setting='to', feed=feed, message=message, **kwargs)

    def log(self):
        super(NoToEmailAddress, self).log()
        _LOG.warning(
            "please run 'r2e email emailaddress' or "
            "'r2e add name url emailaddress'.")


class FeedIndexError (FeedsError, IndexError):
    def __init__(self, index, message=None, **kwargs):
        if message is None:
            message = 'feed {!r} not found'.format(index)
        super(FeedIndexError, self).__init__(
            message=message, **kwargs)
        self.index = index


class OPMLReadError (RSS2EmailError):
    def __init__(self, **kwargs):
        message = 'error reading OPML'
        super(OPMLReadError, self).__init__(message=message, **kwargs)


class ConfigAlreadyExistsError (FeedsError):
    def __init__(self, feeds=None):
        message = 'configuration file already exists'
        super().__init__(feeds=feeds, message=message)
