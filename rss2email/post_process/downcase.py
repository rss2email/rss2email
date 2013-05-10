# Copyright (C) 2013 W. Trevor King <wking@tremily.us>
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

"""A text-manipulation hook for testing the post-processing infrastructure
"""

def _downcase_payload(part):
    if part.get_content_type() != 'text/plain':
        return
    payload = part.get_payload()
    part.set_payload(payload.lower())

def downcase_message(message, **kwargs):
    """Downcase the message body (for testing)
    """
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                _downcase_payload(part)
    else:
        _downcase_payload(message)
    return message
