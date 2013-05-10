# Copyright

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
"""
