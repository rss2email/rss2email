# Copyright (C) 2013 Arun Persaud <apersaud@lbl.gov>
#                    W. Trevor King <wking@tremily.us>
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

"""Post-processing functions for manipulating entry messages

A post-processing hook, when set, is called by ``Feed._process()``
with the following keyword arguments:

feed:
  The ``rss2email.feed.Feed`` instance that generated the message.
parsed:
  The parsed feed as returned by ``feedparser.parse``
entry:
  The entry from ``parsed`` that lead to the current message.
guid:
  The feed's view of the identity of the current entry.
message:
  The ``email.message.Message`` instance that rss2email would send if
  the post-processing hook were disabled.

Post-processing hooks should return the possibly altered message, or
return ``None`` to indicate that the message should not be sent.

For feeds with the ``digest`` setting enabled, there is a similar
``digest-post-process`` hook, which, when set, is called by
``Feed.run()``.  The keyword arguments are mostly the same as for the
standard post-processing hook, however ``entry`` and ``guid`` are
replaced by ``seen``, a list of ``(guid, id_)`` tuples for each entry
part contained in the digest message.
"""
