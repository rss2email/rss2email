# Copyright (C) 2013 Francois Boulogne <fboulogne at april dot org>
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

import urllib
import re
import rss2email

def process(feed, parsed, entry, guid, message):
    # decode message
    encoding = message.get_charsets()[0]
    content = str(message.get_payload(decode=True), encoding)

    # Get the link
    link = entry['link']
    if not link:
        return message

    # Remove the redirect and modify the content
    try:
        request = urllib.request.Request(link)
        request.add_header('User-agent', rss2email.feed._USER_AGENT)
        direct_link = urllib.request.urlopen(request).geturl()
    except:
        return message
    content = re.sub(re.escape(link), direct_link, content, re.MULTILINE)

    # clear CTE and set message. It can be important to clear the CTE
    # before setting the payload, since the payload is only re-encoded
    # if CTE is not already set.
    del message['Content-Transfer-Encoding']
    message.set_payload(content, charset=encoding)

    return message
