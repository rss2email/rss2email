# Copyright

"""Useful hooks for post processing messages

Along with some less useful hooks for testing the post-processing
infrastructure.  The hook, when set, is called by ``Feed._process()``
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

Post processing hooks should return the possibly altered message, or
return ``None`` to indicate that the message should not be sent.
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
