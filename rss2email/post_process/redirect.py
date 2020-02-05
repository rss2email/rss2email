# Copyright (C) 2013-2018 Andrey Zelenchuk <azelenchuk@parallels.com>
#                         François Boulogne <fboulogne sciunto org>
#                         Jakub Wilk <jwilk@jwilk.net>
#                         Profpatsch <mail@profpatsch.de>
#                         Puneeth Chaganti <punchagan@muse-amuse.in>
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

"""Remove redirects on the post URL.

Several websites use redirects (e.g. feedburner) for various reasons like
statistics. You may want to avoid this for privacy or for durability.

This hook finds and uses the real url behind redirects.
"""

import logging as _logging
import re
import urllib

import rss2email


LOG = _logging.getLogger(__name__)


def process(feed, parsed, entry, guid, message):
    # decode message
    encoding = message.get_charsets()[0]
    content = str(message.get_payload(decode=True), encoding)

    links = []

    # Get the link
    link = entry['link']
    if link:
        links.append(link)

    for enclosure in entry['enclosures']:
        links.append(enclosure['href'])

    if not links:
        return message

    # Remove the redirect and modify the content
    timeout = rss2email.config.CONFIG['DEFAULT'].getint('feed-timeout')
    proxy = rss2email.config.CONFIG['DEFAULT']['proxy']
    for link in links:
        try:
            request = urllib.request.Request(link)
            request.add_header('User-agent', feed.user_agent)
            direct_link = urllib.request.urlopen(request).geturl()
        except Exception as e:
            LOG.warning('could not follow redirect for {}: {}'.format(
                link, e))
            continue
        content = re.sub(re.escape(link), direct_link, content)

    # clear CTE and set message. It can be important to clear the CTE
    # before setting the payload, since the payload is only re-encoded
    # if CTE is not already set.
    del message['Content-Transfer-Encoding']
    message.set_payload(content, charset=encoding)

    return message
