#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""rss2email: get RSS feeds emailed to you
http://rss2email.infogami.com

Usage:
  new [emailaddress] (create new feedfile)
  email newemailaddress (update default email)
  run [--no-send] [num]
  add feedurl [emailaddress]
  list
  reset
  delete n
  pause n
  unpause n
  opmlexport
  opmlimport filename
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
        if self.__cause__ is not None:
            LOG.error('cause: {}'.format(e.__cause__))
        LOG.warning((
                'Error attempting to send email via sendmail. You may need '
                'to configure rss2email to use an SMTP server. Please refer '
                'to the rss2email documentation or website ({}) for complete '
                'documentation.').format(__url__))


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
        ('smtp-server', 'smtp.yourisp.net:25'),
        ('smtp-auth', str(False)),      # set to True to use SMTP AUTH
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

def isstr(f): return isinstance(f, type('')) or isinstance(f, type(u''))
def ishtml(t): return type(t) is type(())
def contains(a,b): return a.find(b) != -1
def unu(s): # I / freakin' hate / that unicode
    if type(s) is types.UnicodeType: return s.encode('utf-8')
    else: return s

### Parsing Utilities ###

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

### Simple Database of Feeds ###

class Feed:
    def __init__(self, url, to):
        self.url, self.etag, self.modified, self.seen = url, None, None, {}
        self.active = True
        self.to = to

def load(lock=1):
    if not os.path.exists(feedfile):
        print 'Feedfile "%s" does not exist.  If you\'re using r2e for the first time, you' % feedfile
        print "have to run 'r2e new' first."
        sys.exit(1)
    try:
        feedfileObject = open(feedfile, 'r')
    except IOError, e:
        print "Feedfile could not be opened: %s" % e
        sys.exit(1)
    feeds = pickle.load(feedfileObject)

    if lock:
        locktype = 0
        if unix:
            locktype = fcntl.LOCK_EX
            fcntl.flock(feedfileObject.fileno(), locktype)
        #HACK: to deal with lock caching
        feedfileObject = open(feedfile, 'r')
        feeds = pickle.load(feedfileObject)
        if unix:
            fcntl.flock(feedfileObject.fileno(), locktype)
    if feeds:
        for feed in feeds[1:]:
            if not hasattr(feed, 'active'):
                feed.active = True

    return feeds, feedfileObject

def unlock(feeds, feedfileObject):
    if not unix:
        pickle.dump(feeds, open(feedfile, 'w'))
    else:
        fd = open(feedfile+'.tmp', 'w')
        pickle.dump(feeds, fd)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.rename(feedfile+'.tmp', feedfile)
        fcntl.flock(feedfileObject.fileno(), fcntl.LOCK_UN)

#@timelimit(FEED_TIMEOUT)
def parse(url, etag, modified):
    if PROXY == '':
        return feedparser.parse(url, etag, modified)
    else:
        proxy = urllib2.ProxyHandler( {"http":PROXY} )
        return feedparser.parse(url, etag, modified, handlers = [proxy])


### Program Functions ###

def add(*args):
    if len(args) == 2 and contains(args[1], '@') and not contains(args[1], '://'):
        urls, to = [args[0]], args[1]
    else:
        urls, to = args, None

    feeds, feedfileObject = load()
    if (feeds and not isstr(feeds[0]) and to is None) or (not len(feeds) and to is None):
        print "No email address has been defined. Please run 'r2e email emailaddress' or"
        print "'r2e add url emailaddress'."
        sys.exit(1)
    for url in urls: feeds.append(Feed(url, to))
    unlock(feeds, feedfileObject)

def run(num=None):
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

def list():
    feeds, feedfileObject = load(lock=0)
    default_to = ""

    if feeds and isstr(feeds[0]):
        default_to = feeds[0]; ifeeds = feeds[1:]; i=1
        print "default email:", default_to
    else: ifeeds = feeds; i = 0
    for f in ifeeds:
        active = ('[ ]', '[*]')[f.active]
        print `i`+':',active, f.url, '('+(f.to or ('default: '+default_to))+')'
        if not (f.to or default_to):
            print "   W: Please define a default address with 'r2e email emailaddress'"
        i+= 1

def opmlexport():
    feeds, feedfileObject = load(lock=0)

    if feeds:
        print '<?xml version="1.0" encoding="UTF-8"?>\n<opml version="1.0">\n<head>\n<title>rss2email OPML export</title>\n</head>\n<body>'
        for f in feeds[1:]:
            url = xml.sax.saxutils.escape(f.url)
            print '<outline type="rss" text="%s" xmlUrl="%s"/>' % (url, url)
        print '</body>\n</opml>'

def opmlimport(importfile):
    importfileObject = None
    print 'Importing feeds from', importfile
    if not os.path.exists(importfile):
        print 'OPML import file "%s" does not exist.' % feedfile
    try:
        importfileObject = open(importfile, 'r')
    except IOError, e:
        print "OPML import file could not be opened: %s" % e
        sys.exit(1)
    try:
        dom = xml.dom.minidom.parse(importfileObject)
        newfeeds = dom.getElementsByTagName('outline')
    except:
        print 'E: Unable to parse OPML file'
        sys.exit(1)

    feeds, feedfileObject = load(lock=1)

    for f in newfeeds:
        if f.hasAttribute('xmlUrl'):
            feedurl = f.getAttribute('xmlUrl')
            print 'Adding %s' % xml.sax.saxutils.unescape(feedurl)
            feeds.append(Feed(feedurl, None))

    unlock(feeds, feedfileObject)

def delete(n):
    feeds, feedfileObject = load()
    if (n == 0) and (feeds and isstr(feeds[0])):
        print >>warn, "W: ID has to be equal to or higher than 1"
    elif n >= len(feeds):
        print >>warn, "W: no such feed"
    else:
        print >>warn, "W: deleting feed %s" % feeds[n].url
        feeds = feeds[:n] + feeds[n+1:]
        if n != len(feeds):
            print >>warn, "W: feed IDs have changed, list before deleting again"
    unlock(feeds, feedfileObject)

def toggleactive(n, active):
    feeds, feedfileObject = load()
    if (n == 0) and (feeds and isstr(feeds[0])):
        print >>warn, "W: ID has to be equal to or higher than 1"
    elif n >= len(feeds):
        print >>warn, "W: no such feed"
    else:
        action = ('Pausing', 'Unpausing')[active]
        print >>warn, "%s feed %s" % (action, feeds[n].url)
        feeds[n].active = active
    unlock(feeds, feedfileObject)

def reset():
    feeds, feedfileObject = load()
    if feeds and isstr(feeds[0]):
        ifeeds = feeds[1:]
    else: ifeeds = feeds
    for f in ifeeds:
        if VERBOSE: print "Resetting %d already seen items" % len(f.seen)
        f.seen = {}
        f.etag = None
        f.modified = None

    unlock(feeds, feedfileObject)

def email(addr):
    feeds, feedfileObject = load()
    if feeds and isstr(feeds[0]): feeds[0] = addr
    else: feeds = [addr] + feeds
    unlock(feeds, feedfileObject)

if __name__ == '__main__':
    args = sys.argv
    try:
        if len(args) < 3: raise InputError, "insufficient args"
        feedfile, action, args = args[1], args[2], args[3:]

        if action == "run":
            if args and args[0] == "--no-send":
                def send(sender, recipient, subject, body, contenttype, extraheaders=None, smtpserver=None):
                    if VERBOSE: print 'Not sending:', unu(subject)

            if args and args[-1].isdigit(): run(int(args[-1]))
            else: run()

        elif action == "email":
            if not args:
                raise InputError, "Action '%s' requires an argument" % action
            else:
                email(args[0])

        elif action == "add": add(*args)

        elif action == "new":
            if len(args) == 1: d = [args[0]]
            else: d = []
            pickle.dump(d, open(feedfile, 'w'))

        elif action == "list": list()

        elif action in ("help", "--help", "-h"): print __doc__

        elif action == "delete":
            if not args:
                raise InputError, "Action '%s' requires an argument" % action
            elif args[0].isdigit():
                delete(int(args[0]))
            else:
                raise InputError, "Action '%s' requires a number as its argument" % action

        elif action in ("pause", "unpause"):
            if not args:
                raise InputError, "Action '%s' requires an argument" % action
            elif args[0].isdigit():
                active = (action == "unpause")
                toggleactive(int(args[0]), active)
            else:
                raise InputError, "Action '%s' requires a number as its argument" % action

        elif action == "reset": reset()

        elif action == "opmlexport": opmlexport()

        elif action == "opmlimport":
            if not args:
                raise InputError, "OPML import '%s' requires a filename argument" % action
            opmlimport(args[0])

        else:
            raise InputError, "Invalid action"

    except InputError, e:
        print "E:", e
        print
        print __doc__
