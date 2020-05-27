# -*- encoding: utf-8 -*-
#
# Copyright (C) 2012-2018 Arun Persaud <apersaud@lbl.gov>
#                         Dmitry Bogatov <KAction@gnu.org>
#                         George Saunders <georgesaunders@gmail.com>
#                         Jeff Backus <jeff@jsbackus.com>
#                         Mátyás Jani <jzombi@gmail.com>
#                         Profpatsch <mail@profpatsch.de>
#                         Thiago Coutinho <root@thiagoc.net>
#                         Thibaut Girka <thib@sitedethib.com>
#                         W. Trevor King <wking@tremily.us>
#                         Yannik Sembritzki <yannik@sembritzki.me>
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

"""IMAP feeds management
"""

import email as _email
import imaplib as _imaplib

from . import LOG as _LOG
from . import config as _config
from . import error as _error


def parse_mailbox(config=None, section='DEFAULT'):
    messages = []

    if config is None:
        config = _config.CONFIG
    # connect to imap server
    server = config.get(section, 'imap-server')
    port = config.getint(section, 'imap-port')
    _LOG.debug('reading messages from {}:{}'.format(server, port))
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
            except Exception:
                raise _error.IMAPAuthenticationError(
                    server=server, port=port, username=username)
        # select configured mailbox
        mailbox = config.get(section, 'imap-mailbox')
        res, _ = imap.select(mailbox)
        if res != 'OK':
            raise _error.RSS2EmailError(
                message='mailbox {} does not exist'.format(mailbox))
        # filter emails with sender and prefix
        sender = config.get(section, 'imap-mgt-sender')
        prefix = config.get(section, 'imap-mgt-prefix')
        _, msgnums = imap.search(
            None, '(UNSEEN FROM "{}" SUBJECT "{}")'.format(sender, prefix))
        for num in msgnums[0].split():
            _, content = imap.fetch(num, '(RFC822)')
            msg = _email.message_from_bytes(content[0][1])
            # make sure that it starts with prefix
            if not msg.get('Subject').startswith(prefix):
                continue
            # mark as read
            imap.store(num, '-FLAGS', '\\Seen')
            messages.append(msg)
    finally:
        imap.logout()

    return messages


def parse_messages(messages):
    actions = []

    for msg in messages:
        subject = msg.get('Subject').split()
        action = subject[1]
        if action == 'add':
            body = _get_email_body(msg)
            if not body:
                continue
            url = body.splitlines()[0]
            actions.append({
                'action': action,
                'name': subject[2],
                'url': url,
                })
        elif action == 'delete':
            actions.append({
                'action': action,
                'index': subject[2],
                })
        else:
            _LOG.error('action {} not supported'.format(action))
            continue

    return actions


def _get_email_body(message):
    body = None

    if message.get_content_type() == "text/plain":
        body = str(message.get_payload()).strip()
    elif message.is_multipart():
        for part in message.walk():
            is_text = part.get_content_type() == 'text/plain'
            is_attach = 'attachment' in str(part.get('Content-Disposition'))
            if is_text and not is_attach:
                body = str(part.get_payload()).strip()
    else:
        _LOG.error('email body is not in text/plain format')

    return body
