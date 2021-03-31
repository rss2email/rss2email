# Copyright (C) 2004-2021 Aaron Swartz
#                         Alyssa Ross <hi@alyssa.is>
#                         Anders Damsgaard <anders@adamsgaard.dk>
#                         Andrey Zelenchuk <azelenchuk@parallels.com>
#                         Andrey Zelenchuk <azelenchuk@plesk.com>
#                         Brian Lalor
#                         Dean Jackson
#                         Dmitry Bogatov <KAction@gnu.org>
#                         Erik Hetzner
#                         Etienne Millon <me@emillon.org>
#                         François Boulogne <fboulogne sciunto org>
#                         George Saunders <georgesaunders@gmail.com>
#                         Jakub Wilk <jwilk@jwilk.net>
#                         Joey Hess
#                         Kaashif Hymabaccus <kaashif@kaashif.co.uk>
#                         Lindsey Smith <lindsey.smith@gmail.com>
#                         Léo Gaspard <leo@gaspard.io>
#                         Marcel Ackermann
#                         Martin 'Joey' Schulze
#                         Martin Monperrus <monperrus@users.noreply.github.com>
#                         Matej Cepl
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

"""Per-user rss2email configuration
"""

import collections as _collections
import configparser as _configparser

import html2text as _html2text

class Config (_configparser.ConfigParser):
    def __init__(self, dict_type=_collections.OrderedDict,
                 interpolation=_configparser.ExtendedInterpolation(),
                 **kwargs):
        super(Config, self).__init__(
            dict_type=dict_type, interpolation=interpolation, **kwargs)

    def setup_html2text(self, section='DEFAULT'):
        """Setup html2text globals to match our configuration

        Html2text unfortunately uses globals (instead of keyword
        arguments) to configure its conversion.
        """
        if section not in self:
            section = 'DEFAULT'
        _html2text.config.UNICODE_SNOB = self.getboolean(
            section, 'unicode-snob')
        _html2text.config.LINKS_EACH_PARAGRAPH = self.getboolean(
            section, 'links-after-each-paragraph')
        _html2text.config.INLINE_LINKS = self.getboolean(
            section, 'inline-links')
        _html2text.config.WRAP_LINKS = self.getboolean(
            section, 'wrap-links')
        # hack to prevent breaking the default in every existing config file
        body_width = self.getint(section, 'body-width')
        _html2text.config.BODY_WIDTH = 0 if body_width < 0 else 78 if body_width == 0 else body_width


CONFIG = Config()

# setup defaults for feeds that don't customize
CONFIG['DEFAULT'] = _collections.OrderedDict((
        ### Addressing
        # The email address messages are from by default
        ('from', 'user@rss2email.invalid'),
        # The User-Agent default string (rss2email __VERSION__ and __URL__ is replaced)
        ('user-agent', 'rss2email/__VERSION__ (__URL__)'),
        # Transfer-Encoding. For local mailing it is safe and
        # convenient to use 8bit.
        ('use-8bit', str(False)),
        # True: Only use the 'from' address. Overrides the use-publisher-email setting.
        # False: Use the email address specified by the feed, when possible.
        ('force-from', str(False)),
        # True: Use author's email if found, or use publisher's email if found, or use the 'from' setting.
        # False: Use author's email if found, or use the 'from' setting.
        ('use-publisher-email', str(False)),
        # If empty, only use the feed email address rather than
        # friendly name plus email address.  Available attributes may
        # include 'feed', 'feed-name', 'feed-url', 'feed-title', 'author', and
        # 'publisher', but only 'feed', 'feed-name', and 'feed-url' are guaranteed.
        ('name-format', '{feed-title}: {author}'),
        # Set this to default To email addresses.
        ('to', ''),

        ### Fetching
        # Set an HTTP proxy (e.g. 'http://your.proxy.here:8080/')
        ('proxy', ''),
        # Set the timeout (in seconds) for feed server response
        ('feed-timeout', str(60)),
        # Set the time (in seconds) to sleep between fetches from the same server
        ('same-server-fetch-interval', str(0)),

        ### Processing
        # True: Fetch, process, and email feeds.
        # False: Don't fetch, process, or email feeds
        ('active', str(True)),
        # True: Send a single, multi-entry email per feed per rss2email run.
        # False: Send a single email per entry.
        ('digest', str(False)),
        # True: Generate Date header based on item's date, when possible.
        # False: Generate Date header based on time sent.
        ('date-header', str(False)),
        # A comma-delimited list of some combination of
        # ('issued', 'created', 'modified', 'expired')
        # expressing ordered list of preference in dates
        # to use for the Date header of the email.
        ('date-header-order', 'modified, issued, created, expired'),
        # Set this to add bonus headers to all emails
        # Example: bonus-header = 'Approved: joe@bob.org'
        ('bonus-header', ''),
        # True: Receive one email per post.
        # False: Receive an email every time a post changes.
        ('trust-guid', str(True)),
        # True: Receive one email per unique link url.
        # False: Defer to trust-guid preference.
        # Toggling this for existing feeds may result in duplicates,
        # because the old entries will not be recorded under their new
        # link-based ids.
        ('trust-link', str(False)),
        # If 'trust-guid' or 'trust-link' is True, this setting allows to receive
        # a new email message in reply to the previous one when the post changes.
        ('reply-changes', str(False)),
        # To most correctly encode emails with international
        # characters, we iterate through the list below and use the
        # first character set that works.
        ('encodings', 'US-ASCII, ISO-8859-1, UTF-8, BIG5, ISO-2022-JP'),
        # User processing hooks.  Note the space after the module name.
        # Example: post-process = 'rss2email.post_process.downcase downcase_message'
        ('post-process', ''),
        # User processing hooks for digest messages.  If 'digest' is
        # enabled, the usual 'post-process' hook gets to message the
        # per-entry messages, but this hook is called with the full
        # digest message before it is mailed.
        # Example: digest-post-process = 'rss2email.post_process.downcase downcase_message'
        ('digest-post-process', ''),
        ## HTML conversion
        # True: Send text/html messages when possible.
        # False: Convert HTML to plain text.
        ('html-mail', str(False)),
        ('multipart-html', str(False)),
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
        # Use inline, rather than reference, for formatting images and links.
        ('inline-links', str(True)),
        # Wrap links according to body width.
        ('wrap-links', str(True)),
        # Wrap long lines at position.
        # Any negative value for no wrapping, 0 for 78 width (compatibility), or any positive width.
        ('body-width', str(0)),

        ### Mailing
        # Select protocol from: sendmail, smtp, imap
        ('email-protocol', 'sendmail'),
        # True: Use SMTP_SERVER to send mail.
        # Sendmail (or compatible) configuration
        ('sendmail', '/usr/sbin/sendmail'),  # Path to sendmail (or compatible)
        ('sendmail_config', ''),
        # SMTP configuration
        ('smtp-auth', str(False)),      # set to True to use SMTP AUTH
        ('smtp-username', 'username'),  # username for SMTP AUTH
        ('smtp-password', 'password'),  # password for SMTP AUTH
        ('smtp-server', 'smtp.example.net'),
        ('smtp-port', '465'),
        ('smtp-ssl', str(False)),       # Connect to the SMTP server using SSL
        # IMAP configuration
        ('imap-auth', str(False)),      # set to True to use IMAP auth.
        ('imap-username', 'username'),  # username for IMAP authentication
        ('imap-password', 'password'),  # password for IMAP authentication
        ('imap-server', 'imap.example.net'),
        ('imap-port', str(143)),
        ('imap-ssl', str(False)),       # connect to the IMAP server using SSL
        ('imap-mailbox', 'INBOX'),      # where we should store new messages
        # Maildir configuration
        ('maildir-path', '~/Maildir'),
        ('maildir-mailbox', 'INBOX'),

        ### Miscellaneous
        # Verbosity (one of 'error', 'warning', 'info', or 'debug').
        ('verbose', 'info'),
        ))
