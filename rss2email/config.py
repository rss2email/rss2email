# Copyright (C) 2004-2013 Aaron Swartz
#                         Brian Lalor
#                         Dean Jackson
#                         Erik Hetzner
#                         Etienne Millon <me@emillon.org>
#                         Joey Hess
#                         Lindsey Smith <lindsey.smith@gmail.com>
#                         Marcel Ackermann
#                         Martin 'Joey' Schulze
#                         Matej Cepl
#                         W. Trevor King <wking@tremily.us>
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
        ('from', 'user@rss2email.invalid'),
        # True: Only use the 'from' address.
        # False: Use the email address specified by the feed, when possible.
        ('force-from', str(False)),
        # True: Use the publisher's email if you can't find the author's.
        # False: Just use the 'from' email instead.
        ('use-publisher-email', str(False)),
        # Only use the feed email address rather than friendly name
        # plus email address
        ('friendly-name', str(True)),
        # Set this to default To email addresses.
        ('to', ''),

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
        # Set this to add bonus headers to all emails
        # Example: bonus-header = 'Approved: joe@bob.org'
        ('bonus-header', ''),
        # True: Receive one email per post.
        # False: Receive an email every time a post changes.
        ('trust-guid', str(True)),
        # To most correctly encode emails with international
        # characters, we iterate through the list below and use the
        # first character set that works.
        ('encodings', 'US-ASCII, ISO-8859-1, UTF-8, BIG5, ISO-2022-JP'),
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
