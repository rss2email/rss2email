# -*- encoding: utf-8 -*-
#
# Copyright (C) 2012-2021 Amir Yalon <git@please.nospammail.net>
#                         Arun Persaud <apersaud@lbl.gov>
#                         Dmitry Bogatov <KAction@gnu.org>
#                         George Saunders <georgesaunders@gmail.com>
#                         Jeff Backus <jeff@jsbackus.com>
#                         Léo Gaspard <leo@gaspard.io>
#                         Mátyás Jani <jzombi@gmail.com>
#                         Profpatsch <mail@profpatsch.de>
#                         Thiago Coutinho <root@thiagoc.net>
#                         Thibaut Girka <thib@sitedethib.com>
#                         W. Trevor King <wking@tremily.us>
#                         Yannik Sembritzki <yannik@sembritzki.me>
#                         auouymous <5005204+auouymous@users.noreply.github.com>
#                         auouymous <au@qzx.com>
#                         boyska <piuttosto@logorroici.org>
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

"""Email message generation and dispatching
"""

import email as _email
from email.charset import Charset as _Charset
import email.encoders as _email_encoders
from email.generator import BytesGenerator as _BytesGenerator
import email.header as _email_header
from email.header import Header as _Header
from email.mime.text import MIMEText as _MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr as _formataddr
from email.utils import parseaddr as _parseaddr
import logging
import mailbox as _mailbox
from email.utils import getaddresses as _getaddresses
import imaplib as _imaplib
import io as _io
import smtplib as _smtplib
import ssl as _ssl
import subprocess as _subprocess
import sys as _sys
import time as _time
import os as _os

import html2text

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

def _add_plain_multipart(guid: str, message, html: str):
    headers = message.items()
    msg = MIMEMultipart('alternative')
    for name, value in headers:
        if name.lower().startswith('content-'):
            continue
        msg[str(name)] = value

    html_part = _MIMEText(html, _subtype='html')
    msg.attach(html_part)

    text_content = html2text.html2text(html=html, baseurl=guid)
    text_part = _MIMEText(text_content)
    msg.attach(text_part)
    return msg

def message_add_plain_multipart(guid, message, html):
    if message.get_content_type() == 'text/html':
        m = _add_plain_multipart(guid, message, html)
        return m
    if message.is_multipart():
        # we could support multipart messages, but let's postpone it
        # in fact, we don't expect any multipart message to arrive here
        _LOG.warning("Couldn't add a text/plain part to this multipart message. "
                "If you see this, it's probably a bug in rss2email."
                )
        return message
    return message

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
    recipient_list = []
    for recipient_name, recipient_addr in _getaddresses([recipient]):
        recipient_encoding = guess_encoding(recipient_name, encodings)
        recipient_list.append(_formataddr((recipient_name, recipient_addr),
                                          charset=recipient_encoding))

    subject_encoding = guess_encoding(subject, encodings)
    body_encoding = guess_encoding(body, encodings)

    # Create the message ('plain' stands for Content-Type: text/plain)
    message = _MIMEText(body, content_type, body_encoding)
    message['From'] = sender
    message['To'] = ', '.join(recipient_list)
    message['Subject'] = _Header(subject, subject_encoding)
    if config.getboolean(section, 'use-8bit'):
        del message['Content-Transfer-Encoding']
        charset = _Charset(body_encoding)
        charset.body_encoding = _email_encoders.encode_7or8bit
        message.set_payload(body, charset=charset)
    if extra_headers:
        for key,value in extra_headers.items():
            encoding = guess_encoding(value, ['US-ASCII'] + encodings)
            message[key] = _Header(value, encoding)
    if config.getboolean(section, 'multipart-html'):
        message = message_add_plain_multipart(
                guid=str(message.get('x-rss-url', '')),
                message=message,
                html=body)
    return message

def smtp_send(recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    server = config.get(section, 'smtp-server')
    # Adding back in support for 'server:port'
    pos = server.find(':')
    if 0 <= pos:
        # Strip port out of server name
        port = int(server[pos+1:])
        server = server[:pos]
    else:
        port = config.getint(section, 'smtp-port')

    _LOG.debug('sending message to {} via {}'.format(recipient, server))
    ssl = config.getboolean(section, 'smtp-ssl')
    smtp_auth = config.getboolean(section, 'smtp-auth')
    try:
        if ssl or smtp_auth:
            context = _ssl.create_default_context()
        if ssl:
            smtp = _smtplib.SMTP_SSL(host=server, port=port, context=context)
        else:
            smtp = _smtplib.SMTP(host=server, port=port)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        raise _error.SMTPConnectionError(server=server) from e
    if smtp_auth:
        username = config.get(section, 'smtp-username')
        password = config.get(section, 'smtp-password')
        try:
            if not ssl:
                smtp.starttls(context=context)
            smtp.login(username, password)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            raise _error.SMTPAuthenticationError(
                server=server, username=username)
    smtp.send_message(message, config.get(section, 'from'), recipient.split(','))
    smtp.quit()

def imap_send(message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    server = config.get(section, 'imap-server')
    port = config.getint(section, 'imap-port')
    _LOG.debug('sending message to {}:{}'.format(server, port))
    ssl = config.getboolean(section, 'imap-ssl')
    if ssl:
        imap = _imaplib.IMAP4_SSL(server, port)
    else:
        imap = _imaplib.IMAP4(server, port)
    try:
        if config.getboolean(section, 'imap-auth'):
            username = config.get(section, 'imap-username')
            password = config.get(section, 'imap-password')
            try:
                if not ssl:
                    imap.starttls()
                imap.login(username, password)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                raise _error.IMAPAuthenticationError(
                    server=server, port=port, username=username)
        mailbox = config.get(section, 'imap-mailbox')
        date = _imaplib.Time2Internaldate(_time.localtime())
        message_bytes = _flatten(message)
        imap.append(mailbox, None, date, message_bytes)
    finally:
        imap.logout()

def maildir_send(message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    path = config.get(section, 'maildir-path')
    mailbox = config.get(section, 'maildir-mailbox')
    maildir = _mailbox.Maildir(_os.path.join(path, mailbox))
    maildir.add(message)

def _decode_header(header):
    """Decode RFC-2047-encoded headers to Unicode strings

    >>> from email.header import Header
    >>> _decode_header('abc')
    'abc'
    >>> _decode_header('=?utf-8?b?zpbOtc+Nz4I=?= <z@olympus.org>')
    'Ζεύς <z@olympus.org>'
    >>> _decode_header(Header('Ζεύς <z@olympus.org>', 'utf-8'))
    'Ζεύς <z@olympus.org>'
    """
    if isinstance(header, _Header):
        return str(header)
    chunks = []
    for chunk,charset in _email_header.decode_header(header):
        if charset is None:
            if isinstance(chunk, bytes):
                chunk = str(chunk, 'ascii')
            chunks.append(chunk)
        else:
            chunks.append(str(chunk, charset))
    return ''.join(chunks)

def _flatten(message):
    r"""Flatten an email.message.Message to bytes

    >>> import rss2email.config
    >>> config = rss2email.config.Config()
    >>> config.read_dict(rss2email.config.CONFIG)

    Here's a 7-bit, base64 version:

    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\n",
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
    b'WW91J3JlIGdyZWF0LCDOls61z43PgiEK'
    b''

    Here's an 8-bit version:

    >>> config.set('DEFAULT', 'use-8bit', str(True))
    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\n",
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
    b"You're great, \xce\x96\xce\xb5\xcf\x8d\xcf\x82!"
    b''

    Here's an 8-bit version in UTF-16:

    >>> config.set('DEFAULT', 'encodings', 'US-ASCII, UTF-16-LE')
    >>> message = get_message(
    ...     sender='John <jdoe@a.com>', recipient='Ζεύς <z@olympus.org>',
    ...     subject='Homage',
    ...     body="You're great, Ζεύς!\n",
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
    b"\x00Y\x00o\x00u\x00'\x00r\x00e\x00 \x00g\x00r\x00e\x00a\x00t\x00,\x00 \x00\x96\x03\xb5\x03\xcd\x03\xc2\x03!\x00\n\x00"
    """
    bytesio = _io.BytesIO()
    # TODO: use policies argument instead of policy set in `message`
    # see https://docs.python.org/3.6/library/email.generator.html?highlight=bytesgenerator#email.generator.BytesGenerator
    generator = _BytesGenerator(bytesio)
    try:
        generator.flatten(message)
    except UnicodeEncodeError as e:
        # HACK: work around deficiencies in BytesGenerator
        _LOG.warning(e)
        b = message.as_string().encode(str(message.get_charset()))
        m = _email.message_from_bytes(b)
        if not m:
            raise
        h = {k:_decode_header(v) for k,v in m.items()}
        head = {k:_decode_header(v) for k,v in message.items()}
        body = str(m.get_payload(decode=True), str(m.get_charsets()[0]))
        if (h == head and body == message.get_payload()):
            return b
        raise
    else:
        return bytesio.getvalue()

def sendmail_send(recipient, message, config=None, section='DEFAULT'):
    if config is None:
        config = _config.CONFIG
    message_bytes = _flatten(message)
    sendmail = [config.get(section, 'sendmail')]
    sendmail_config = config.get(section, 'sendmail_config')
    if sendmail_config:
        sendmail.extend(['-C', sendmail_config])
    sender_name,sender_addr = _parseaddr(config.get(section, 'from'))
    _LOG.debug(
        'sending message to {} via {}'.format(recipient, sendmail))
    try:
        p = _subprocess.Popen(
            sendmail + ['-F', sender_name, '-f', sender_addr, recipient],
            stdin=_subprocess.PIPE, stdout=_subprocess.PIPE,
            stderr=_subprocess.STDOUT)
        stdout, _ = p.communicate(message_bytes)
        status = p.wait()
        _LOG.debug(stdout.decode())
        if status:
            if _LOG.level > logging.DEBUG:
                _LOG.error(stdout.decode())
            raise _error.SendmailError(status=status)
    except Exception as e:
        raise _error.SendmailError() from e

def send(recipient, message, config=None, section='DEFAULT'):
    protocol = config.get(section, 'email-protocol')
    if protocol == 'smtp':
        smtp_send(
            recipient=recipient, message=message,
            config=config, section=section)
    elif protocol == 'imap':
        imap_send(message=message, config=config, section=section)
    elif protocol == 'maildir':
        maildir_send(message=message, config=config, section=section)
    else:
        sendmail_send(
            recipient=recipient, message=message,
            config=config, section=section)
