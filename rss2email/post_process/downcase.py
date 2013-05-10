# Copyright

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
