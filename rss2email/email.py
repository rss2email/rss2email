# -*- encoding: utf-8 -*-
#
# Copyright (C) 2012-2013 W. Trevor King <wking@tremily.us>
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

"""Email message generation and dispatching
"""

from email.charset import Charset as _Charset
import email.encoders as _email_encoders
from email.header import Header as _Header
from email.mime.text import MIMEText as _MIMEText
from email.utils import formataddr as _formataddr
from email.utils import parseaddr as _parseaddr
import smtplib as _smtplib
import subprocess as _subprocess

from . import LOG as _LOG
from . import config as _config
from . import error as _error


def guess_encoding(string, encodings=('US-ASCII', 'UTF-8')):
    """Find an encoding capable of encoding `string`.

    >>> guess_encoding('alpha', encodings=('US-ASCII', 'UTF-8'))
    'US-ASCII'
    >>> guess_encoding('α', encodings=('US-ASCII', 'UTF-8'))
    'UTF-8'
    >>> guess_encoding('α', encodings=('US-ASCII', 'ISO-8859-1'))
    Traceback (most recent call last):
      ...
    rss2email.error.NoValidEncodingError: no valid encoding for α in ('US-ASCII', 'ISO-8859-1')
    """
    for encoding in encodings:
        try:
            string.encode(encoding)
        except (UnicodeError, LookupError):
            pass
        else:
            return encoding
    raise _error.NoValidEncodingError(string=string, encodings=encodings)

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
        config = _config.CONFIG
    if section not in config.sections():
        section = 'DEFAULT'
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
    if config.getboolean(section, 'use-8bit'):
        del message['Content-Transfer-Encoding']
        charset = _Charset(body_encoding)
        charset.body_encoding = _email_encoders.encode_7or8bit
        message.set_payload(body, charset=charset)
    if extra_headers:
        for key,value in extra_headers.items():
            encoding = guess_encoding(value, encodings)
            message[key] = _Header(value, encoding)
    return message

def smtp_send(sender, recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    server = config.get(section, 'smtp-server')
    _LOG.debug('sending message to {} via {}'.format(recipient, server))
    ssl = config.getboolean(section, 'smtp-ssl')
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
        raise _error.SMTPConnectionError(server=server) from e
    if config.getboolean(section, 'smtp-auth'):
        username = config.get(section, 'smtp-username')
        password = config.get(section, 'smtp-password')
        try:
            if not ssl:
                smtp.starttls()
            smtp.login(username, password)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            raise _error.SMTPAuthenticationError(
                server=server, username=username)
    smtp.send_message(message, sender, [recipient])
    smtp.quit()

def _flatten(message):
    r"""Flatten an email.message.Message to bytes

    >>> import rss2email.config
    >>> config = rss2email.config.Config()
    >>> config.read_dict(rss2email.config.CONFIG)

    Here's a 7-bit, base64 version:

    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\\n",
    ...     content_type='plain',
    ...     config=config)
    >>> for line in _flatten(message).split(b'\n'):
    ...     print(line)  # doctest: +REPORT_UDIFF
    b'MIME-Version: 1.0'
    b'Content-Type: text/plain; charset="utf-8"'
    b'Content-Transfer-Encoding: base64'
    b'From: John <jdoe@a.com>'
    b'To: =?utf-8?b?zpbOtc+Nz4I=?= <z@olympus.org>'
    b'Subject: Homage'
    b''
    b'WW91J3JlIGdyZWF0LCDOls61z43PgiFcbg=='
    b''

    Here's an 8-bit version:

    >>> config.set('DEFAULT', 'use-8bit', str(True))
    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\\n",
    ...     content_type='plain',
    ...     config=config)
    >>> for line in _flatten(message).split(b'\n'):
    ...     print(line)  # doctest: +REPORT_UDIFF
    b'MIME-Version: 1.0'
    b'Content-Type: text/plain; charset="utf-8"'
    b'From: John <jdoe@a.com>'
    b'To: =?utf-8?b?zpbOtc+Nz4I=?= <z@olympus.org>'
    b'Subject: Homage'
    b'Content-Transfer-Encoding: 8bit'
    b''
    b"You're great, \xce\x96\xce\xb5\xcf\x8d\xcf\x82!\\n"

    Here's an 8-bit version in UTF-16:

    >>> config.set('DEFAULT', 'encodings', 'US-ASCII, UTF-16-LE')
    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\\n",
    ...     content_type='plain',
    ...     config=config)
    >>> for line in _flatten(message).split(b'\n'):
    ...     print(line)  # doctest: +REPORT_UDIFF
    b'MIME-Version: 1.0'
    b'Content-Type: text/plain; charset="utf-16-le"'
    b'From: John <jdoe@a.com>'
    b'To: =?utf-8?b?zpbOtc+Nz4I=?= <z@olympus.org>'
    b'Subject: Homage'
    b'Content-Transfer-Encoding: 8bit'
    b''
    b"\x00Y\x00o\x00u\x00'\x00r\x00e\x00 \x00g\x00r\x00e\x00a\x00t\x00,\x00 \x00\x96\x03\xb5\x03\xcd\x03\xc2\x03!\x00\\\x00n\x00"
    """
    return message.as_string().encode(str(message.get_charset()))

def sendmail_send(sender, recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    message_bytes = _flatten(message)
    _LOG.debug(
        'sending message to {} via /usr/sbin/sendmail'.format(recipient))
    try:
        p = _subprocess.Popen(
            ['/usr/sbin/sendmail', '-f', sender, recipient],
            stdin=_subprocess.PIPE, stdout=_subprocess.PIPE,
            stderr=_subprocess.PIPE)
        stdout,stderr = p.communicate(message_bytes)
        status = p.wait()
        if status:
            raise _error.SendmailError(
                status=status, stdout=stdout, stderr=stderr)
    except Exception as e:
        raise _error.SendmailError() from e

def send(sender, recipient, message, config=None, section='DEFAULT'):
    if config.getboolean(section, 'use-smtp'):
        smtp_send(sender, recipient, message)
    else:
        sendmail_send(sender, recipient, message)
