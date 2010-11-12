### Options for configuring rss2email ###

# The email address messages are from by default:
DEFAULT_FROM = "bozo@dev.null.invalid"

# 1: Send text/html messages when possible.
# 0: Convert HTML to plain text.
HTML_MAIL = 1

# 1: Only use the DEFAULT_FROM address.
# 0: Use the email address specified by the feed, when possible.
FORCE_FROM = 0

# 1: Receive one email per post.
# 0: Receive an email every time a post changes.
TRUST_GUID = 1

# 1: Generate Date header based on item's date, when possible.
# 0: Generate Date header based on time sent.
DATE_HEADER = 1

# A tuple consisting of some combination of
# ('issued', 'created', 'modified', 'expired')
# expressing ordered list of preference in dates 
# to use for the Date header of the email.
DATE_HEADER_ORDER = ('modified', 'issued', 'created')

# 1: Apply Q-P conversion (required for some MUAs).
# 0: Send message in 8-bits.
# http://cr.yp.to/smtp/8bitmime.html
#DEPRECATED 
QP_REQUIRED = 0
#DEPRECATED 
	
# 1: Name feeds as they're being processed.
# 0: Keep quiet.
VERBOSE = 0

# 1: Use the publisher's email if you can't find the author's.
# 0: Just use the DEFAULT_FROM email instead.
USE_PUBLISHER_EMAIL = 0

# 1: Use SMTP_SERVER to send mail.
# 0: Call /usr/sbin/sendmail to send mail.
SMTP_SEND = 1

SMTP_SERVER = "smtp.yourisp.net:25"
AUTHREQUIRED = 0 # if you need to use SMTP AUTH set to 1
SMTP_USER = 'username'  # for SMTP AUTH, set SMTP username here
SMTP_PASS = 'password'  # for SMTP AUTH, set SMTP password here

# Connect to the SMTP server using SSL

SMTP_SSL = 0



# Set this to add a bonus header to all emails (start with '\n').
BONUS_HEADER = ''
# Example: BONUS_HEADER = '\nApproved: joe@bob.org'

# Set this to override From addresses. Keys are feed URLs, values are new titles.
OVERRIDE_FROM = {}

# Set this to override From email addresses. Keys are feed URLs, values are new emails.

OVERRIDE_EMAIL = {}



# Set this to default From email addresses. Keys are feed URLs, values are new email addresses.

DEFAULT_EMAIL = {}


# Only use the email from address rather than friendly name plus email address

NO_FRIENDLY_NAME = 0



# Set this to override the timeout (in seconds) for feed server response
FEED_TIMEOUT = 60

# Optional CSS styling
USE_CSS_STYLING = 1
STYLE_SHEET='h1 {font: 18pt Georgia, "Times New Roman";} body {font: 12pt Arial;} a:link {font: 12pt Arial; font-weight: bold; color: #0000cc} blockquote {font-family: monospace; }  .header { background: #e0ecff; border-bottom: solid 4px #c3d9ff; padding: 5px; margin-top: 0px; color: red;} .header a { font-size: 20px; text-decoration: none; } .footer { background: #c3d9ff; border-top: solid 4px #c3d9ff; padding: 5px; margin-bottom: 0px; } #entry {border: solid 4px #c3d9ff; } #body { margin-left: 5px; margin-right: 5px; }'

# If you have an HTTP Proxy set this in the format 'http://your.proxy.here:8080/'
PROXY=""

# To most correctly encode emails with international characters, we iterate through the list below and use the first character set that works
# Eventually (and theoretically) ISO-8859-1 and UTF-8 are our catch-all failsafes
CHARSET_LIST='US-ASCII', 'BIG5', 'ISO-2022-JP', 'ISO-8859-1', 'UTF-8'
