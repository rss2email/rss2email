#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""rss2email: get RSS feeds emailed to you
"""

__version__ = '2.71'
__url__ = 'http://rss2email.infogami.com'
__author__ = 'Lindsey Smith (lindsey@allthingsrss.com)'
__copyright__ = '(C) 2004 Aaron Swartz. GNU GPL 2 or 3.'
___contributors__ = [
    'Dean Jackson',
    'Brian Lalor',
    'Joey Hess',
    'Matej Cepl',
    "Martin 'Joey' Schulze",
    'Marcel Ackermann (http://www.DreamFlasher.de)',
    'Lindsey Smith (maintainer)',
    'Erik Hetzner',
    'Aaron Swartz (original author)',
    ]

import collections as _collections
import configparser as _configparser
from email.mime.text import MIMEText as _MIMEText
from email.header import Header as _Header
from email.utils import parseaddr as _parseaddr
from email.utils import formataddr as _formataddr
import hashlib as _hashlib
import logging as _logging
import os as _os
import pickle as _pickle
import re as _re
import smtplib as _smtplib
import socket as _socket
import subprocess as _subprocess
import sys as _sys
import threading as _threading
import time as _time
import traceback as _traceback
import types as _types
import urllib.request as _urllib_request
import xml.dom.minidom as _minidom
import xml.sax.saxutils as _saxutils

UNIX = False
try:
    import fcntl as _fcntl
    # A pox on SunOS file locking methods
    if 'sunos' not in sys.platform:
        UNIX = True
except:
    pass

import feedparser as _feedparser
import html2text as _html2text


LOG = _logging.getLogger('rss2email')
LOG.addHandler(_logging.StreamHandler())
LOG.setLevel(_logging.ERROR)

_feedparser.USER_AGENT = 'rss2email/{} +{}'.format(__version__, __url__)
_urllib_request.install_opener(_urllib_request.build_opener())
_SOCKET_ERRORS = []
for e in ['error', 'gaierror']:
    if hasattr(_socket, e):
        _SOCKET_ERRORS.append(getattr(_socket, e))


class RSS2EmailError (Exception):
    def log(self):
        LOG.error(str(self))
        if self.__cause__ is not None:
            LOG.error('cause: {}'.format(e.__cause__))


class TimeoutError (RSS2EmailError):
    def __init__(self, time_limited_function, message=None):
        if message is None:
            if time_limited_function.error is not None:
                message = (
                    'error while running time limited function: {}'.format(
                        time_limited_function.error[1]))
            else:
                message = '{} second timeout exceeded'.format(
                    time_limited_function.timeout)
        super(TimeoutError, self).__init__(message)
        self.time_limited_function = time_limited_function


class NoValidEncodingError (ValueError, RSS2EmailError):
    def __init__(self, string, encodings):
        msg = 'no valid encoding for {} in {}'.format(string, encodings)
        super(NoValidEncodingError, self).__init__(msg)
        self.string = string
        self.encodings = encodings


class SMTPConnectionError (ValueError, RSS2EmailError):
    def __init__(self, server, message=None):
        if message is None:
            message = 'could not connect to mail server {}'.format(server)
        super(SMTPConnectionError, self).__init__(message)
        self.server = server

    def log(self):
        super(SMTPConnectionError, self).log()
        LOG.warning(
            'check your config file to confirm that smtp-server and other '
            'mail server settings are configured properly')
        if hasattr(e.__cause__, 'reason'):
            LOG.error('reason: {}'.format(e.__cause__.reason))


class SMTPAuthenticationError (SMTPConnectionError):
    def __init__(self, server, username):
        message = (
            'could not authenticate with mail server {} as user {}'.format(
                server, username))
        super(SMTPConnectionError, self).__init__(
            server=server, message=message)
        self.server = server
        self.username = username


class SendmailError (RSS2EmailError):
    def __init__(self, status=None, stdout=None, stderr=None):
        if status:
            message = 'sendmail exited with code {}'.format(status)
        else:
            message = ''
        super(SendmailError, self).__init__(message)
        self.status = status
        self.stdout = stdout
        self.stderr = stderr

    def log(self):
        super(SendmailError, self).log()
        LOG.warning((
                'Error attempting to send email via sendmail. You may need '
                'to configure rss2email to use an SMTP server. Please refer '
                'to the rss2email documentation or website ({}) for complete '
                'documentation.').format(__url__))


class FeedError (RSS2EmailError):
    def __init__(self, feed, message=None):
        if message is None:
            message = 'error with feed {}'.format(feed.name)
        super(FeedError, self).__init__(message)
        self.feed = feed


class InvalidFeedName (FeedError):
    def __init__(self, name, **kwargs):
        message = "invalid feed name '{}'".format(name)
        super(InvalidFeedName, self).__init__(message=message, **kwargs)


class FeedsError (RSS2EmailError):
    def __init__(self, feeds, message=None):
        if message is None:
            message = 'error with feeds'
        super(FeedsError, self).__init__(message)
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
        LOG.warning(
            "if you're using r2e for the first time, you have to run "
            "'r2e new' first.")


class NoToEmailAddress (FeedsError):
    def __init__(self, **kwargs):
        message = 'no target email address has been defined'
        super(NoToEmailAddress, self).__init__(message=message, **kwargs)

    def log(self):
        super(NoToEmailAddress, self).log()
        LOG.warning(
            "please run 'r2e email emailaddress' or "
            "'r2e add name url emailaddress'.")


class OPMLReadError (RSS2EmailError):
    def __init__(self, **kwargs):
        message = 'error reading OPML'
        super(RSS2EmailError, self).__init__(message=message, **kwargs)


class Config (_configparser.ConfigParser):
    def __init__(self, **kwargs):
        super(Config, self).__init__(dict_type=_collections.OrderedDict)

    def _setup(self, section='DEFAULT'):
        _html2text.UNICODE_SNOB = self.getboolean(
            section, 'unicode-snob', fallback=False)
        _html2text.LINKS_EACH_PARAGRAPH = self.getboolean(
            section, 'links-after-each-paragaph', fallback=False)
        _html2text.BODY_WIDTH = self.getint(section, 'body-width', fallback=0)


CONFIG = Config()

# setup defaults for feeds that don't customize
CONFIG['DEFAULT'] = _collections.OrderedDict((
        ### Addressing
        # The email address messages are from by default
        ('from', 'bozo@dev.null.invalid'),
        # True: Only use the 'from' address.
        # False: Use the email address specified by the feed, when possible.
        ('force-from', str(False)),
        # True: Use the publisher's email if you can't find the author's.
        # False: Just use the 'from' email instead.
        ('use-publisher-email', str(False)),
        # Only use the feed email address rather than friendly name
        # plus email address
        ('friendly-name', str(True)),
        # Set this to override From addresses.
        ('override-from', str(False)),
        # Set this to default To email addresses.
        ('to', ''),
        # Set this to override To email addresses.
        ('override-to', False),

        ### Fetching
        # Set an HTTP proxy (e.g. 'http://your.proxy.here:8080/')
        ('proxy', ''),
        # Set the timeout (in seconds) for feed server response
        ('feed-timeout', str(60)),

        ### Processing
        # True: Fetch, process, and email feeds.
        # False: Don't fetch, process, or email feeds
        ('active', str(True)),
        # True: Generate Date header based on item's date, when possible.
        # False: Generate Date header based on time sent.
        ('date-header', str(False)),
        # A comma-delimited list of some combination of
        # ('issued', 'created', 'modified', 'expired')
        # expressing ordered list of preference in dates
        # to use for the Date header of the email.
        ('date-header-order', 'modified, issued, created, expired'),
        # Set this to add a bonus header to all emails (start with '\n').
        # Example: bonus-header = '\nApproved: joe@bob.org'
        ('bonus-header', ''),
        # True: Receive one email per post.
        # False: Receive an email every time a post changes.
        ('trust-guid', str(True)),
        # To most correctly encode emails with international
        # characters, we iterate through the list below and use the
        # first character set that works Eventually (and
        # theoretically) UTF-8 is our catch-all failsafe.
        ('encodings', 'US-ASCII, BIG5, ISO-2022-JP, ISO-8859-1, UTF-8'),
        ## HTML conversion
        # True: Send text/html messages when possible.
        # False: Convert HTML to plain text.
        ('html-mail', str(False)),
        # Optional CSS styling
        ('use-css', str(False)),
        ('css', (
                'h1 {\n'
                '  font: 18pt Georgia, "Times New Roman";\n'
                '}\n'
                'body {\n'
                '  font: 12pt Arial;\n'
                '}\n'
                'a:link {\n'
                '  font: 12pt Arial;\n'
                '  font-weight: bold;\n'
                '  color: #0000cc;\n'
                '}\n'
                'blockquote {\n'
                '  font-family: monospace;\n'
                '}\n'
                '.header {\n'
                '  background: #e0ecff;\n'
                '  border-bottom: solid 4px #c3d9ff;\n'
                '  padding: 5px;\n'
                '  margin-top: 0px;\n'
                '  color: red;\n'
                '}\n'
                '.header a {\n'
                '  font-size: 20px;\n'
                '  text-decoration: none;\n'
                '}\n'
                '.footer {\n'
                '  background: #c3d9ff;\n'
                '  border-top: solid 4px #c3d9ff;\n'
                '  padding: 5px;\n'
                '  margin-bottom: 0px;\n'
                '}\n'
                '#entry {\n'
                '  border: solid 4px #c3d9ff;\n'
                '}\n'
                '#body {\n'
                '  margin-left: 5px;\n'
                '  margin-right: 5px;\n'
                '}\n')),
        ## html2text options
        # Use Unicode characters instead of their ascii psuedo-replacements
        ('unicode-snob', str(False)),
        # Put the links after each paragraph instead of at the end.
        ('links-after-each-paragraph', str(False)),
        # Wrap long lines at position. 0 for no wrapping.
        ('body-width', str(0)),

        ### Mailing
        # True: Use SMTP_SERVER to send mail.
        # False: Call /usr/sbin/sendmail to send mail.
        ('use-smtp', str(False)),
        ('smtp-server', 'smtp.yourisp.net:25'),        ('smtp-auth', str(False)),      # set to True to use SMTP AUTH
        ('smtp-username', 'username'),  # username for SMTP AUTH
        ('smtp-password', 'password'),  # password for SMTP AUTH
        ('smtp-ssl', str(False)),       # Connect to the SMTP server using SSL

        ### Miscellaneous
        # Verbosity (one of 'error', 'warning', 'info', or 'debug').
        ('verbose', 'warning'),
        ))


def guess_encoding(string, encodings=('US-ASCII', 'UTF-8')):
    """Find an encodign capable of encoding `string`.

    >>> guess_encoding('alpha', encodings=('US-ASCII', 'UTF-8'))
    'US-ASCII'
    >>> guess_encoding('α', encodings=('US-ASCII', 'UTF-8'))
    'UTF-8'
    >>> guess_encoding('α', encodings=('US-ASCII', 'ISO-8859-1'))
    Traceback (most recent call last):
      ...
    rss2email.NoValidEncodingError: no valid encoding for α in ('US-ASCII', 'ISO-8859-1')
    """
    for encoding in encodings:
        try:
            string.encode(encoding)
        except (UnicodeError, LookupError):
            pass
        else:
            return encoding
    raise NoValidEncodingError(string=string, encodings=encodings)

def get_message(sender, recipient, subject, body, content_type,
                extra_headers=None, config=None, section='DEFAULT'):
    """Generate a `Message` instance.

    All arguments should be Unicode strings (plain ASCII works as well).

    Only the real name part of sender and recipient addresses may contain
    non-ASCII characters.

    The email will be properly MIME encoded.

    The charset of the email will be the first one out of the list
    that can represent all the characters occurring in the email.

    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Testing',
    ...     body='Hello, world!\\n',
    ...     content_type='plain',
    ...     extra_headers={'Approved': 'joe@bob.org'})
    >>> print(message.as_string())  # doctest: +REPORT_UDIFF
    MIME-Version: 1.0
    Content-Type: text/plain; charset="us-ascii"
    Content-Transfer-Encoding: 7bit
    From: John <jdoe@a.com>
    To: =?utf-8?b?zpbOtc+Nz4I=?= <z@olympus.org>
    Subject: Testing
    Approved: joe@bob.org
    <BLANKLINE>
    Hello, world!
    <BLANKLINE>
    """
    if config is None:
        config = CONFIG
    encodings = [
        x.strip() for x in config.get(section, 'encodings').split(',')]

    # Split real name (which is optional) and email address parts
    sender_name,sender_addr = _parseaddr(sender)
    recipient_name,recipient_addr = _parseaddr(recipient)

    sender_encoding = guess_encoding(sender_name, encodings)
    recipient_encoding = guess_encoding(recipient_name, encodings)
    subject_encoding = guess_encoding(subject, encodings)
    body_encoding = guess_encoding(body, encodings)

    # We must always pass Unicode strings to Header, otherwise it will
    # use RFC 2047 encoding even on plain ASCII strings.
    sender_name = str(_Header(sender_name, sender_encoding).encode())
    recipient_name = str(_Header(recipient_name, recipient_encoding).encode())

    # Make sure email addresses do not contain non-ASCII characters
    sender_addr.encode('ascii')
    recipient_addr.encode('ascii')

    # Create the message ('plain' stands for Content-Type: text/plain)
    message = _MIMEText(body, content_type, body_encoding)
    message['From'] = _formataddr((sender_name, sender_addr))
    message['To'] = _formataddr((recipient_name, recipient_addr))
    message['Subject'] = _Header(subject, subject_encoding)
    for key,value in extra_headers.items():
        encoding = guess_encoding(value, encodings)
        message[key] = _Header(value, encoding)
    return message

def smtp_send(sender, recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = CONFIG
    server = CONFIG.get(section, 'smtp-server')
    ssl = CONFIG.getboolean(section, 'smtp-ssl')
    if ssl:
        smtp = _smtplib.SMTP_SSL()
    else:
        smtp = _smtplib.SMTP()
        smtp.ehlo()
    try:
        smtp.connect(SMTP_SERVER)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        raise SMTPConnectionError(server=server) from e
    if CONFIG.getboolean(section, 'smtp-auth'):
        username = CONFIG.get(section, 'smtp-username')
        password = CONFIG.get(section, 'smtp-password')
        try:
            if not ssl:
                smtp.starttls()
            smtp.login(username, password)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            raise SMTPAuthenticationError(server=server, username=username)
    smtp.send_message(message, sender, [recipient])
    smtp.quit()

def sendmail_send(sender, recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = CONFIG
    try:
        p = _subprocess.Popen(
            ['/usr/sbin/sendmail', recipient],
            stdin=_subprocess.PIPE, stdout=_subprocess.PIPE,
            stderr=_subprocess.PIPE)
        stdout,stderr = p.communicate(message.as_string())
        status = p.wait()
        if status:
            raise SendmailError(status=status, stdout=stdout, stderr=stderr)
    except Exception as e:
        raise SendmailError() from e

def send(sender, recipient, message, config=None, section='DEFAULT'):
    if configSMTP_SEND:
        smtp_send(sender, recipient, message)
    else:
        sendmail_send(sender, recipient, message)


class TimeLimitedFunction (_threading.Thread):
    """Run `function` with a time limit of `timeout` seconds.

    >>> import time
    >>> def sleeping_return(sleep, x):
    ...     time.sleep(sleep)
    ...     return x
    >>> TimeLimitedFunction(0.5, sleeping_return)(0.1, 'x')
    'x'
    >>> TimeLimitedFunction(0.5, sleeping_return)(10, 'y')
    Traceback (most recent call last):
      ...
    rss2email.TimeoutError: 0.5 second timeout exceeded
    >>> TimeLimitedFunction(0.5, time.sleep)('x')
    Traceback (most recent call last):
      ...
    rss2email.TimeoutError: error while running time limited function: a float is required
    """
    def __init__(self, timeout, target, **kwargs):
        super(TimeLimitedFunction, self).__init__(target=target, **kwargs)
        self.setDaemon(True)  # daemon kwarg only added in Python 3.3.
        self.timeout = timeout
        self.result = None
        self.error = None

    def run(self):
        """Based on Thread.run().

        We add handling for self.result and self.error.
        """
        try:
            if self._target:
                self.result = self._target(*self._args, **self._kwargs)
        except:
            self.error = _sys.exc_info()
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.start()
        self.join(self.timeout)
        if self.error:
            raise TimeoutError(time_limited_function=self) from self.error[1]
        elif self.isAlive():
            raise TimeoutError(time_limited_function=self)
        return self.result


def getContent(entry, HTMLOK=0):
    """Select the best content from an entry, deHTMLizing if necessary.
    If raw HTML is best, an ('HTML', best) tuple is returned. """

    # How this works:
    #  * We have a bunch of potential contents.
    #  * We go thru looking for our first choice.
    #    (HTML or text, depending on HTMLOK)
    #  * If that doesn't work, we go thru looking for our second choice.
    #  * If that still doesn't work, we just take the first one.
    #
    # Possible future improvement:
    #  * Instead of just taking the first one
    #    pick the one in the "best" language.
    #  * HACK: hardcoded HTMLOK, should take a tuple of media types

    conts = entry.get('content', [])

    if entry.get('summary_detail', {}):
        conts += [entry.summary_detail]

    if conts:
        if HTMLOK:
            for c in conts:
                if contains(c.type, 'html'): return ('HTML', c.value)

        if not HTMLOK: # Only need to convert to text if HTML isn't OK
            for c in conts:
                if contains(c.type, 'html'):
                    return html2text(c.value)

        for c in conts:
            if c.type == 'text/plain': return c.value

        return conts[0].value

    return ""

def getID(entry):
    """Get best ID from an entry."""
    if TRUST_GUID:
        if 'id' in entry and entry.id:
            # Newer versions of feedparser could return a dictionary
            if type(entry.id) is DictType:
                return entry.id.values()[0]

            return entry.id

    content = getContent(entry)
    if content and content != "\n": return hash(unu(content)).hexdigest()
    if 'link' in entry: return entry.link
    if 'title' in entry: return hash(unu(entry.title)).hexdigest()

def getName(r, entry):
    """Get the best name."""

    if NO_FRIENDLY_NAME: return ''

    feed = r.feed
    if hasattr(r, "url") and r.url in OVERRIDE_FROM.keys():
        return OVERRIDE_FROM[r.url]

    name = feed.get('title', '')

    if 'name' in entry.get('author_detail', []): # normally {} but py2.1
        if entry.author_detail.name:
            if name: name += ": "
            det=entry.author_detail.name
            try:
                name +=  entry.author_detail.name
            except UnicodeDecodeError:
                name +=  unicode(entry.author_detail.name, 'utf-8')

    elif 'name' in feed.get('author_detail', []):
        if feed.author_detail.name:
            if name: name += ", "
            name += feed.author_detail.name

    return name

def validateEmail(email, planb):
    """Do a basic quality check on email address, but return planb if email doesn't appear to be well-formed"""
    email_parts = email.split('@')
    if len(email_parts) != 2:
        return planb
    return email

def getEmail(r, entry):
    """Get the best email_address. If the best guess isn't well-formed (something@somthing.com), use DEFAULT_FROM instead"""

    feed = r.feed

    if FORCE_FROM: return DEFAULT_FROM

    if hasattr(r, "url") and r.url in OVERRIDE_EMAIL.keys():
        return validateEmail(OVERRIDE_EMAIL[r.url], DEFAULT_FROM)

    if 'email' in entry.get('author_detail', []):
        return validateEmail(entry.author_detail.email, DEFAULT_FROM)

    if 'email' in feed.get('author_detail', []):
        return validateEmail(feed.author_detail.email, DEFAULT_FROM)

    if USE_PUBLISHER_EMAIL:
        if 'email' in feed.get('publisher_detail', []):
            return validateEmail(feed.publisher_detail.email, DEFAULT_FROM)

        if feed.get("errorreportsto", ''):
            return validateEmail(feed.errorreportsto, DEFAULT_FROM)

    if hasattr(r, "url") and r.url in DEFAULT_EMAIL.keys():
        return DEFAULT_EMAIL[r.url]
    return DEFAULT_FROM


class Feed (object):
    """Utility class for feed manipulation and storage.

    >>> import pickle
    >>> import sys

    >>> feed = Feed(
    ...    name='test-feed', url='http://example.com/feed.atom', to='a@b.com')
    >>> print(feed)
    test-feed (http://example.com/feed.atom -> a@b.com)
    >>> feed.section
    'feed.test-feed'
    >>> feed.from_email
    'bozo@dev.null.invalid'

    >>> feed.from_email = 'a@b.com'
    >>> feed.save_to_config()
    >>> feed.config.write(sys.stdout)  # doctest: +REPORT_UDIFF, +ELLIPSIS
    [DEFAULT]
    from = bozo@dev.null.invalid
    ...
    verbose = warning
    <BLANKLINE>
    [feed.test-feed]
    url = http://example.com/feed.atom
    from = a@b.com
    to = a@b.com
    <BLANKLINE>

    >>> feed.etag = 'dummy etag'
    >>> string = pickle.dumps(feed)
    >>> feed = pickle.loads(string)
    >>> feed.load_from_config(config=CONFIG)
    >>> feed.etag
    'dummy etag'
    >>> feed.url
    'http://example.com/feed.atom'

    Names can only contain ASCII letters, digits, and '._-'.  Here the
    invalid space causes an exception:

    >>> Feed(name='invalid name')
    Traceback (most recent call last):
      ...
    rss2email.InvalidFeedName: invalid feed name 'invalid name'

    Cleanup `CONFIG`.

    >>> CONFIG['DEFAULT']['to'] = ''
    >>> test_section = CONFIG.pop('feed.test-feed')
    """
    _name_regexp = _re.compile('^[a-zA-Z0-9._-]+$')

    # saved/loaded from feed.dat using __getstate__/__setstate__.
    _dynamic_attributes = [
        'name',
        'etag',
        'modified',
        'seen',
        ]

    ## saved/loaded from ConfigParser instance
    # attributes that aren't in DEFAULT
    _non_default_configured_attributes = [
        'url',
        ]
    # attributes that are in DEFAULT
    _default_configured_attributes = [
        key.replace('-', '_') for key in CONFIG['DEFAULT'].keys()]
    _default_configured_attributes[
        _default_configured_attributes.index('from')
        ] = 'from_email'  # `from` is a Python keyword
    # all attributes that are saved/loaded from .config
    _configured_attributes = (
        _non_default_configured_attributes + _default_configured_attributes)
    # attribute name -> .config option
    _configured_attribute_translations = dict(
        (attr,attr) for attr in _non_default_configured_attributes)
    _configured_attribute_translations.update(dict(
            zip(_default_configured_attributes, CONFIG['DEFAULT'].keys())))
    # .config option -> attribute name
    _configured_attribute_inverse_translations = dict(
        (v,k) for k,v in _configured_attribute_translations.items())

    # hints for value conversion
    _boolean_attributes = [
        'force_from',
        'use_publisher_email',
        'friendly_name',
        'override_from',
        'override_to',
        'active',
        'date_header',
        'trust_guid',
        'html_mail',
        'use_css',
        'unicode_snob',
        'links_after_each_paragraph',
        'use_smtp',
        'smtp_ssl',
        ]

    _integer_attributes = [
        'feed_timeout',
        'body_width',
        ]

    _list_attributes = [
        'date_header_order',
        'encodings',
        ]

    def __init__(self, name=None, url=None, to=None, config=None):
        self._set_name(name=name)
        self.reset()
        self.__setstate__(dict(
                (attr, getattr(self, attr))
                for attr in self._dynamic_attributes))
        self.load_from_config(config)
        if url:
            self.url = url
        if to:
            self.to = to

    def __str__(self):
        return '{} ({} -> {})'.format(self.name, self.url, self.to)

    def __repr__(self):
        return '<Feed {}>'.format(str(self))

    def __getstate__(self):
        "Save dyamic attributes"
        return dict(
            (key,getattr(self,key)) for key in self._dynamic_attributes)

    def __setstate__(self, state):
        "Restore dynamic attributes"
        keys = sorted(state.keys())
        if keys != sorted(self._dynamic_attributes):
            raise ValueError(state)
        self._set_name(name=state['name'])
        self.__dict__.update(state)

    def save_to_config(self):
        "Save configured attributes"
        data = _collections.OrderedDict()
        default = self.config['DEFAULT']
        for attr in self._configured_attributes:
            key = self._configured_attribute_translations[attr]
            value = getattr(self, attr)
            if value is not None:
                value = self._get_configured_option_value(
                    attribute=attr, value=value)
                if (attr in self._non_default_configured_attributes or
                    value != default[key]):
                    data[key] = value
        self.config[self.section] = data

    def load_from_config(self, config=None):
        "Restore configured attributes"
        if config is None:
            config = CONFIG
        self.config = CONFIG
        if self.section in self.config:
            data = self.config[self.section]
        else:
            data = self.config['DEFAULT']
        keys = sorted(data.keys())
        expected = sorted(self._configured_attribute_translations.values())
        if keys != expected:
            for key in expected:
                if (key not in keys and
                    key not in self._non_default_configured_attributes):
                    raise ValueError('missing key: {}'.format(key))
            for key in keys:
                if key not in expected:
                    raise ValueError('extra key: {}'.format(key))
        data = dict(
            (self._configured_attribute_inverse_translations[k],
             self._get_configured_attribute_value(
                  attribute=self._configured_attribute_inverse_translations[k],
                  key=k, data=data))
            for k in data.keys())
        for attr in self._non_default_configured_attributes:
            if attr not in data:
                data[attr] = None
        self.__dict__.update(data)

    def _get_configured_option_value(self, attribute, value):
        if value and attribute in self._list_attributes:
            return ', '.join(value)
        return str(value)

    def _get_configured_attribute_value(self, attribute, key, data):
        if attribute in self._boolean_attributes:
            return data.getboolean(key)
        elif attribute in self._integer_attributes:
            return data.getint(key)
        elif attribute in self._list_attributes:
            return [x.strip() for x in data[key].split(',')]
        return data[key]

    def reset(self):
        """Reset dynamic data
        """
        self.etag = None
        self.modified = None
        self.seen = {}

    def _set_name(self, name):
        if not self._name_regexp.match(name):
            raise InvalidFeedName(name=name, feed=self)
        self.name = name
        self.section = 'feed.{}'.format(self.name)

    def fetch(self):
        """Fetch and parse a feed using feedparser.

        >>> feed = Feed(
        ...    name='test-feed',
        ...    url='http://feeds.feedburner.com/allthingsrss/hJBr')
        >>> parsed = feed.fetch()
        >>> parsed.status
        200
        """
        if self.section in self.config:
            config = self.config[self.section]
        else:
            config = self.config['DEFAULT']
        proxy = config['proxy']
        timeout = config.getint('feed-timeout')
        kwargs = {}
        if proxy:
            kwargs['handlers'] = [_urllib_request.ProxyHandler({'http':proxy})]
        f = TimeLimitedFunction(timeout, _feedparser.parse)
        return f(self.url, self.etag, modified=self.modified, **kwargs)


class Feeds (list):
    """Utility class for rss2email activity.

    >>> import pickle
    >>> import tempfile

    Setup a temporary directory to load.

    >>> tmpdir = tempfile.TemporaryDirectory(prefix='rss2email-test-')
    >>> configfile = _os.path.join(tmpdir.name, 'config')
    >>> with open(configfile, 'w') as f:
    ...     count = f.write('[DEFAULT]\\n')
    ...     count = f.write('to = a@b.com\\n')
    ...     count = f.write('[feed.f1]\\n')
    ...     count = f.write('url = http://a.net/feed.atom\\n')
    ...     count = f.write('to = x@y.net\\n')
    ...     count = f.write('[feed.f2]\\n')
    ...     count = f.write('url = http://b.com/rss.atom\\n')
    >>> datafile = _os.path.join(tmpdir.name, 'feeds.dat')
    >>> with open(datafile, 'wb') as f:
    ...     pickle.dump([
    ...             Feed(name='f1'),
    ...             Feed(name='f2'),
    ...             ], f)

    >>> feeds = Feeds(configdir=tmpdir.name)
    >>> feeds.load()
    >>> for feed in feeds:
    ...     print(feed)
    f1 (http://a.net/feed.atom -> x@y.net)
    f2 (http://b.com/rss.atom -> a@b.com)

    You can index feeds by array index or by feed name.

    >>> feeds[0]
    <Feed f1 (http://a.net/feed.atom -> x@y.net)>
    >>> feeds[-1]
    <Feed f2 (http://b.com/rss.atom -> a@b.com)>
    >>> feeds['f1']
    <Feed f1 (http://a.net/feed.atom -> x@y.net)>
    >>> feeds['missing']
    Traceback (most recent call last):
      ...
    IndexError: missing

    Tweak the feed configuration and save.

    >>> feeds[0].to = None
    >>> feeds.save()
    >>> print(open(configfile, 'r').read().rstrip('\\n'))
    ... # doctest: +REPORT_UDIFF, +ELLIPSIS
    [DEFAULT]
    from = bozo@dev.null.invalid
    ...
    verbose = warning
    <BLANKLINE>
    [feed.f1]
    url = http://a.net/feed.atom
    <BLANKLINE>
    [feed.f2]
    url = http://b.com/rss.atom

    Cleanup the temporary directory.

    >>> tmpdir.cleanup()
    """
    def __init__(self, configdir=None, datafile=None, configfiles=None,
                 config=None):
        super(Feeds, self).__init__()
        if configdir is None:
            configdir = _os.path.expanduser(_os.path.join(
                    '~', '.config', 'rss2email'))
        if datafile is None:
            datafile = _os.path.join(configdir, 'feeds.dat')
        self.datafile = datafile
        if configfiles is None:
            configfiles = [_os.path.join(configdir, 'config')]
        self.configfiles = configfiles
        if config is None:
            config = CONFIG
        self.config = config
        self._datafile_lock = None

    def __getitem__(self, key):
        for feed in self:
            if feed.name == key:
                return feed
        try:
            index = int(key)
        except ValueError as e:
            raise IndexError(key) from e
        return super(Feeds, self).__getitem__(index)

    def __append__(self, feed):
        feed.load_from_config(self.config)
        feed = super(Feeds, self).append(feed)

    def __pop__(self, index=-1):
        feed = super(Feeds, self).pop(index=index)
        if feed.section in self.config:
            self.config.pop(feed.section)
        return feed

    def index(self, index):
        if isinstance(index, int):
            return self[index]
        elif isinstance(index, str):
            try:
                index = int(index)
            except ValueError:
                pass
            else:
                return self.index(index)
            for feed in self:
                if feed.name == index:
                    return feed
        super(Feeds, self).index(index)

    def remove(self, feed):
        super(Feeds, self).remove(feed)
        if feed.section in self.config:
            self.config.pop(feed.section)

    def clear(self):
        while self:
            self.pop(0)

    def load(self, lock=True):
        LOG.debug('load feed configuration from {}'.format(self.configfiles))
        if self.configfiles:
            self.read_configfiles = self.config.read(self.configfiles)
        else:
            self.read_configfiles = []
        LOG.debug('loaded confguration from {}'.format(self.read_configfiles))
        self._load_feeds(lock=lock)

    def _load_feeds(self, lock):
        LOG.debug('load feed data from {}'.format(self.datafile))
        if not _os.path.exists(self.datafile):
            raise NoDataFile(feeds=self)
        try:
            self._datafile_lock = open(self.datafile, 'rb')
        except IOError as e:
            raise DataFileError(feeds=self) from e

        locktype = 0
        if lock and UNIX:
            locktype = _fcntl.LOCK_EX
            _fcntl.flock(self._datafile_lock.fileno(), locktype)

        self.clear()
        self.extend(_pickle.load(self._datafile_lock))

        if locktype == 0:
            self._datafile_lock.close()
            self._datafile_lock = None

        for feed in self:
            feed.load_from_config(self.config)

    def save(self):
        LOG.debug('save feed configuration to {}'.format(self.configfiles[-1]))
        for feed in self:
            feed.save_to_config()
        dirname = _os.path.dirname(self.configfiles[-1])
        if not _os.path.isdir(dirname):
            _os.makedirs(dirname)
        with open(self.configfiles[-1], 'w') as f:
            self.config.write(f)
        self._save_feeds()

    def _save_feeds(self):
        LOG.debug('save feed data to {}'.format(self.datafile))
        dirname = _os.path.dirname(self.datafile)
        if not _os.path.isdir(dirname):
            _os.makedirs(dirname)
        if UNIX:
            tmpfile = self.datafile + '.tmp'
            with open(tmpfile, 'wb') as f:
                _pickle.dump(list(self), f)
            _os.rename(tmpfile, self.datafile)
            if self._datafile_lock is not None:
                self._datafile_lock.close()  # release the lock
                self._datafile_lock = None
        else:
            _pickle.dump(list(self), open(self.datafile, 'wb'))

    def new_feed(self, name=None, prefix='feed-', **kwargs):
        """Return a new feed, possibly auto-generating a name.

        >>> feeds = Feeds()
        >>> print(feeds.new_feed(name='my-feed'))
        my-feed (None -> a@b.com)
        >>> print(feeds.new_feed())
        feed-0 (None -> a@b.com)
        >>> print(feeds.new_feed())
        feed-1 (None -> a@b.com)
        """
        if name is None:
            i = 0
            while True:
                name = '{}{}'.format(prefix, i)
                feed_names = [feed.name for feed in self]
                if name not in feed_names:
                    break
                i += 1
        feed = Feed(name=name, **kwargs)
        self.append(feed)
        return feed


### Program Functions ###

def cmd_new(feeds, args):
    "Create a new feed database."
    if args.email:
        LOG.info('set the default target email to {}'.format(args.email))
        feeds.config['DEFAULT']['to'] = args.email
    feeds.save()

def cmd_email(feeds, args):
    "Update the default target email address"
    if not args.email:
        LOG.info('unset the default target email')
    else:
        LOG.info('set the default target email to {}'.format(args.email))
    feeds.config['DEFAULT']['to'] = args.email
    feeds.save()

def cmd_add(feeds, args):
    "Add a new feed to the database"
    feed = feeds.new_feed(name=args.name, url=args.url, to=args.email)
    LOG.info('add new feed {}'.format(feed))
    if not feed.to:
        raise NoToEmailAddress(feeds=feeds)
    feeds.save()

def cmd_run(feeds, args):
    "Fetch feeds and send entry emails."
    feeds, feedfileObject = load()
    smtpserver = None
    try:
        # We store the default to address as the first item in the feeds list.
        # Here we take it out and save it for later.
        default_to = ""
        if feeds and isstr(feeds[0]): default_to = feeds[0]; ifeeds = feeds[1:]
        else: ifeeds = feeds

        if num: ifeeds = [feeds[num]]
        feednum = 0

        for f in ifeeds:
            try:
                feednum += 1
                if not f.active: continue

                if VERBOSE: print >>warn, 'I: Processing [%d] "%s"' % (feednum, f.url)
                r = {}
                try:
                    r = timelimit(FEED_TIMEOUT, parse)(f.url, f.etag, f.modified)
                except TimeoutError:
                    print >>warn, 'W: feed [%d] "%s" timed out' % (feednum, f.url)
                    continue

                # Handle various status conditions, as required
                if 'status' in r:
                    if r.status == 301: f.url = r['url']
                    elif r.status == 410:
                        print >>warn, "W: feed gone; deleting", f.url
                        feeds.remove(f)
                        continue

                http_status = r.get('status', 200)
                if VERBOSE > 1: print >>warn, "I: http status", http_status
                http_headers = r.get('headers', {
                  'content-type': 'application/rss+xml',
                  'content-length':'1'})
                exc_type = r.get("bozo_exception", Exception()).__class__
                if http_status != 304 and not r.entries and not r.get('version', ''):
                    if http_status not in [200, 302]:
                        print >>warn, "W: error %d [%d] %s" % (http_status, feednum, f.url)

                    elif contains(http_headers.get('content-type', 'rss'), 'html'):
                        print >>warn, "W: looks like HTML [%d] %s"  % (feednum, f.url)

                    elif http_headers.get('content-length', '1') == '0':
                        print >>warn, "W: empty page [%d] %s" % (feednum, f.url)

                    elif hasattr(socket, 'timeout') and exc_type == socket.timeout:
                        print >>warn, "W: timed out on [%d] %s" % (feednum, f.url)

                    elif exc_type == IOError:
                        print >>warn, 'W: "%s" [%d] %s' % (r.bozo_exception, feednum, f.url)

                    elif hasattr(feedparser, 'zlib') and exc_type == feedparser.zlib.error:
                        print >>warn, "W: broken compression [%d] %s" % (feednum, f.url)

                    elif exc_type in _SOCKET_ERRORS:
                        exc_reason = r.bozo_exception.args[1]
                        print >>warn, "W: %s [%d] %s" % (exc_reason, feednum, f.url)

                    elif exc_type == urllib2.URLError:
                        if r.bozo_exception.reason.__class__ in _SOCKET_ERRORS:
                            exc_reason = r.bozo_exception.reason.args[1]
                        else:
                            exc_reason = r.bozo_exception.reason
                        print >>warn, "W: %s [%d] %s" % (exc_reason, feednum, f.url)

                    elif exc_type == AttributeError:
                        print >>warn, "W: %s [%d] %s" % (r.bozo_exception, feednum, f.url)

                    elif exc_type == KeyboardInterrupt:
                        raise r.bozo_exception

                    elif r.bozo:
                        print >>warn, 'E: error in [%d] "%s" feed (%s)' % (feednum, f.url, r.get("bozo_exception", "can't process"))

                    else:
                        print >>warn, "=== rss2email encountered a problem with this feed ==="
                        print >>warn, "=== See the rss2email FAQ at http://www.allthingsrss.com/rss2email/ for assistance ==="
                        print >>warn, "=== If this occurs repeatedly, send this to lindsey@allthingsrss.com ==="
                        print >>warn, "E:", r.get("bozo_exception", "can't process"), f.url
                        print >>warn, r
                        print >>warn, "rss2email", __version__
                        print >>warn, "feedparser", feedparser.__version__
                        print >>warn, "html2text", h2t.__version__
                        print >>warn, "Python", sys.version
                        print >>warn, "=== END HERE ==="
                    continue

                r.entries.reverse()

                for entry in r.entries:
                    id = getID(entry)

                    # If TRUST_GUID isn't set, we get back hashes of the content.
                    # Instead of letting these run wild, we put them in context
                    # by associating them with the actual ID (if it exists).

                    frameid = entry.get('id')
                    if not(frameid): frameid = id
                    if type(frameid) is DictType:
                        frameid = frameid.values()[0]

                    # If this item's ID is in our database
                    # then it's already been sent
                    # and we don't need to do anything more.

                    if frameid in f.seen:
                        if f.seen[frameid] == id: continue

                    if not (f.to or default_to):
                        print "No default email address defined. Please run 'r2e email emailaddress'"
                        print "Ignoring feed %s" % f.url
                        break

                    if 'title_detail' in entry and entry.title_detail:
                        title = entry.title_detail.value
                        if contains(entry.title_detail.type, 'html'):
                            title = html2text(title)
                    else:
                        title = getContent(entry)[:70]

                    title = title.replace("\n", " ").strip()

                    datetime = time.gmtime()

                    if DATE_HEADER:
                        for datetype in DATE_HEADER_ORDER:
                            kind = datetype+"_parsed"
                            if kind in entry and entry[kind]: datetime = entry[kind]

                    link = entry.get('link', "")

                    from_addr = getEmail(r, entry)

                    name = h2t.unescape(getName(r, entry))
                    fromhdr = formataddr((name, from_addr,))
                    tohdr = (f.to or default_to)
                    subjecthdr = title
                    datehdr = time.strftime("%a, %d %b %Y %H:%M:%S -0000", datetime)
                    useragenthdr = "rss2email"

                    # Add post tags, if available
                    tagline = ""
                    if 'tags' in entry:
                        tags = entry.get('tags')
                        taglist = []
                        if tags:
                            for tag in tags:
                                taglist.append(tag['term'])
                        if taglist:
                            tagline = ",".join(taglist)

                    extraheaders = {'Date': datehdr, 'User-Agent': useragenthdr, 'X-RSS-Feed': f.url, 'X-RSS-ID': id, 'X-RSS-URL': link, 'X-RSS-TAGS' : tagline}
                    if BONUS_HEADER != '':
                        for hdr in BONUS_HEADER.strip().splitlines():
                            pos = hdr.strip().find(':')
                            if pos > 0:
                                extraheaders[hdr[:pos]] = hdr[pos+1:].strip()
                            else:
                                print >>warn, "W: malformed BONUS HEADER", BONUS_HEADER

                    entrycontent = getContent(entry, HTMLOK=HTML_MAIL)
                    contenttype = 'plain'
                    content = ''
                    if USE_CSS_STYLING and HTML_MAIL:
                        contenttype = 'html'
                        content = "<html>\n"
                        content += '<head><style><!--' + STYLE_SHEET + '//--></style></head>\n'
                        content += '<body>\n'
                        content += '<div id="entry">\n'
                        content += '<h1'
                        content += ' class="header"'
                        content += '><a href="'+link+'">'+subjecthdr+'</a></h1>\n'
                        if ishtml(entrycontent):
                            body = entrycontent[1].strip()
                        else:
                            body = entrycontent.strip()
                        if body != '':
                            content += '<div id="body"><table><tr><td>\n' + body + '</td></tr></table></div>\n'
                        content += '\n<p class="footer">URL: <a href="'+link+'">'+link+'</a>'
                        if hasattr(entry,'enclosures'):
                            for enclosure in entry.enclosures:
                                if (hasattr(enclosure, 'url') and enclosure.url != ""):
                                    content += ('<br/>Enclosure: <a href="'+enclosure.url+'">'+enclosure.url+"</a>\n")
                                if (hasattr(enclosure, 'src') and enclosure.src != ""):
                                    content += ('<br/>Enclosure: <a href="'+enclosure.src+'">'+enclosure.src+'</a><br/><img src="'+enclosure.src+'"\n')
                        if 'links' in entry:
                            for extralink in entry.links:
                                if ('rel' in extralink) and extralink['rel'] == u'via':
                                    extraurl = extralink['href']
                                    extraurl = extraurl.replace('http://www.google.com/reader/public/atom/', 'http://www.google.com/reader/view/')
                                    viatitle = extraurl
                                    if ('title' in extralink):
                                        viatitle = extralink['title']
                                    content += '<br/>Via: <a href="'+extraurl+'">'+viatitle+'</a>\n'
                        content += '</p></div>\n'
                        content += "\n\n</body></html>"
                    else:
                        if ishtml(entrycontent):
                            contenttype = 'html'
                            content = "<html>\n"
                            content = ("<html><body>\n\n" +
                                       '<h1><a href="'+link+'">'+subjecthdr+'</a></h1>\n\n' +
                                       entrycontent[1].strip() + # drop type tag (HACK: bad abstraction)
                                       '<p>URL: <a href="'+link+'">'+link+'</a></p>' )

                            if hasattr(entry,'enclosures'):
                                for enclosure in entry.enclosures:
                                    if enclosure.url != "":
                                        content += ('Enclosure: <a href="'+enclosure.url+'">'+enclosure.url+"</a><br/>\n")
                            if 'links' in entry:
                                for extralink in entry.links:
                                    if ('rel' in extralink) and extralink['rel'] == u'via':
                                        content += 'Via: <a href="'+extralink['href']+'">'+extralink['title']+'</a><br/>\n'

                            content += ("\n</body></html>")
                        else:
                            content = entrycontent.strip() + "\n\nURL: "+link
                            if hasattr(entry,'enclosures'):
                                for enclosure in entry.enclosures:
                                    if enclosure.url != "":
                                        content += ('\nEnclosure: ' + enclosure.url + "\n")
                            if 'links' in entry:
                                for extralink in entry.links:
                                    if ('rel' in extralink) and extralink['rel'] == u'via':
                                        content += '<a href="'+extralink['href']+'">Via: '+extralink['title']+'</a>\n'

                    smtpserver = send(fromhdr, tohdr, subjecthdr, content, contenttype, extraheaders, smtpserver)

                    f.seen[frameid] = id

                f.etag, f.modified = r.get('etag', None), r.get('modified', None)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                print >>warn, "=== rss2email encountered a problem with this feed ==="
                print >>warn, "=== See the rss2email FAQ at http://www.allthingsrss.com/rss2email/ for assistance ==="
                print >>warn, "=== If this occurs repeatedly, send this to lindsey@allthingsrss.com ==="
                print >>warn, "E: could not parse", f.url
                traceback.print_exc(file=warn)
                print >>warn, "rss2email", __version__
                print >>warn, "feedparser", feedparser.__version__
                print >>warn, "html2text", h2t.__version__
                print >>warn, "Python", sys.version
                print >>warn, "=== END HERE ==="
                continue

    finally:
        unlock(feeds, feedfileObject)
        if smtpserver:
            smtpserver.quit()

def cmd_list(feeds, args):
    "List all the feeds in the database"
    for i,feed in enumerate(feeds):
        if feed.active:
            active_char = '*'
        else:
            active_char = ' '
        print('{}: [{}] {}'.format(i, active_char, feed))

def _cmd_set_active(feeds, args, active=True):
    "Shared by `cmd_pause` and `cmd_unpause`."
    if active:
        action = 'unpause'
    else:
        action = 'pause'
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        LOG.info('{} feed {}'.format(action, feed))
        feed.active = active
    feeds.save()

def cmd_pause(feeds, args):
    "Pause a feed (disable fetching)"
    _cmd_set_active(feeds=feeds, args=args, active=False)

def cmd_unpause(feeds, args):
    "Unpause a feed (enable fetching)"
    _cmd_set_active(feeds=feeds, args=args, active=True)

def cmd_delete(feeds, args):
    "Remove a feed from the database"
    to_remove = []
    for index in args.index:
        feed = feeds.index(index)
        to_remove.append(feed)
    for feed in to_remove:
        LOG.info('deleting feed {}'.format(feed))
        feeds.remove(feed)
    feeds.save()

def cmd_reset(feeds, args):
    "Forget dynamic feed data (e.g. to re-send old entries)"
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        LOG.info('resetting feed {}'.format(feed))
        feed.reset()
    feeds.save()

def cmd_opmlimport(feeds, args):
    "Import configuration from OPML."
    if args.file:
        LOG.info('importing feeds from {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        LOG.info('importing feeds from stdin')
        f = _sys.stdin
    try:
        dom = _minidom.parse(f)
        new_feeds = dom.getElementsByTagName('outline')
    except Exception as e:
        raise OPMLReadError() from e
    if args.file:
        f.close()
    for feed in new_feeds:
        if feed.hasAttribute('xmlUrl'):
            url = _saxutils.unescape(feed.getAttribute('xmlUrl'))
            feed = feeds.new_feed(url=url)
            LOG.info('add new feed {}'.format(feed))
    feeds.save()

def cmd_opmlexport(feeds, args):
    "Export configuration to OPML."
    if args.file:
        LOG.info('exporting feeds to {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        LOG.info('exporting feeds to stdout')
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


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, version=__version__)

    parser.add_argument(
        '-c', '--config', metavar='PATH', nargs='*',
        help='path to the configuration file')
    parser.add_argument(
        '-d', '--data', metavar='PATH',
        help='path to the feed data file')
    parser.add_argument(
        '-V', '--verbose', default=0, action='count',
        help='increment verbosity')
    subparsers = parser.add_subparsers(title='commands')

    new_parser = subparsers.add_parser(
        'new', help=cmd_new.__doc__.splitlines()[0])
    new_parser.set_defaults(func=cmd_new)
    new_parser.add_argument(
        'email', nargs='?',
        help='default target email for the new feed database')

    email_parser = subparsers.add_parser(
        'email', help=cmd_email.__doc__.splitlines()[0])
    email_parser.set_defaults(func=cmd_email)
    email_parser.add_argument(
        'email', default='',
        help='default target email for the email feed database')

    add_parser = subparsers.add_parser(
        'add', help=cmd_add.__doc__.splitlines()[0])
    add_parser.set_defaults(func=cmd_add)
    add_parser.add_argument(
        'name', help='name of the new feed')
    add_parser.add_argument(
        'url', help='location of the new feed')
    add_parser.add_argument(
        'email', nargs='?',
        help='target email for the new feed')

    run_parser = subparsers.add_parser(
        'run', help=cmd_run.__doc__.splitlines()[0])
    run_parser.set_defaults(func=cmd_run)
    run_parser.add_argument(
        '-n', '--no-send', dest='send',
        default=True, action='store_const', const=False,
        help="fetch feeds, but don't send email")
    run_parser.add_argument(
        'index', nargs='*',
        help='feeds to fetch (defaults to fetching all feeds)')

    list_parser = subparsers.add_parser(
        'list', help=cmd_list.__doc__.splitlines()[0])
    list_parser.set_defaults(func=cmd_list)

    pause_parser = subparsers.add_parser(
        'pause', help=cmd_pause.__doc__.splitlines()[0])
    pause_parser.set_defaults(func=cmd_pause)
    pause_parser.add_argument(
        'index', nargs='*',
        help='feeds to pause (defaults to pausing all feeds)')

    unpause_parser = subparsers.add_parser(
        'unpause', help=cmd_unpause.__doc__.splitlines()[0])
    unpause_parser.set_defaults(func=cmd_unpause)
    unpause_parser.add_argument(
        'index', nargs='*',
        help='feeds to ununpause (defaults to pausing all feeds)')

    delete_parser = subparsers.add_parser(
        'delete', help=cmd_delete.__doc__.splitlines()[0])
    delete_parser.set_defaults(func=cmd_delete)
    delete_parser.add_argument(
        'index', nargs='+',
        help='feeds to delete')

    reset_parser = subparsers.add_parser(
        'reset', help=cmd_reset.__doc__.splitlines()[0])
    reset_parser.set_defaults(func=cmd_reset)
    reset_parser.add_argument(
        'index', nargs='*',
        help='feeds to reset (defaults to resetting all feeds)')

    opmlimport_parser = subparsers.add_parser(
        'opmlimport', help=cmd_opmlimport.__doc__.splitlines()[0])
    opmlimport_parser.set_defaults(func=cmd_opmlimport)
    opmlimport_parser.add_argument(
        'file', metavar='PATH', nargs='?',
        help='path for imported OPML (defaults to stdin)')

    opmlexport_parser = subparsers.add_parser(
        'opmlexport', help=cmd_opmlexport.__doc__.splitlines()[0])
    opmlexport_parser.set_defaults(func=cmd_opmlexport)
    opmlexport_parser.add_argument(
        'file', metavar='PATH', nargs='?',
        help='path for exported OPML (defaults to stdout)')

    args = parser.parse_args()

    if args.verbose:
        LOG.setLevel(max(_logging.DEBUG, _logging.ERROR - 10 * args.verbose))

    try:
        feeds = Feeds(datafile=args.data, configfiles=args.config)
        if args.func != cmd_new:
            lock = args.func not in [cmd_list, cmd_opmlexport]
            feeds.load(lock=lock)
        args.func(feeds=feeds, args=args)
    except RSS2EmailError as e:
        e.log()
        _sys.exit(1)
