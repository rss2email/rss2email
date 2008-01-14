#!/usr/bin/python
"""rss2email: get RSS feeds emailed to you
http://rss2email.infogami.com

Usage:
  new [emailaddress] (create new feedfile)
  email newemailaddress (update default email)
  run [--no-send] [num]
  add feedurl [emailaddress]
  list
  delete n
"""
__version__ = "2.62"
__author__ = "Aaron Swartz (me@aaronsw.com)"
__copyright__ = "(C) 2004 Aaron Swartz. GNU GPL 2."
___contributors__ = ["Dean Jackson", "Brian Lalor", "Joey Hess", 
                     "Matej Cepl", "Martin 'Joey' Schulze", 
                     "Marcel Ackermann (http://www.DreamFlasher.de)", 
                     "Lindsey Smith (lindsey.smith@gmail.com)" ]

### Vaguely Customizable Options ###

# The email address messages are from by default:
DEFAULT_FROM = "bozo@dev.null.invalid"

# 1: Send text/html messages when possible.
# 0: Convert HTML to plain text.
HTML_MAIL = 0

# 1: Only use the DEFAULT_FROM address.
# 0: Use the email address specified by the feed, when possible.
FORCE_FROM = 0

# 1: Receive one email per post.
# 0: Receive an email every time a post changes.
TRUST_GUID = 1

# 1: Generate Date header based on item's date, when possible.
# 0: Generate Date header based on time sent.
DATE_HEADER = 0

# A tuple consisting of some combination of
# ('issued', 'created', 'modified', 'expired')
# expressing ordered list of preference in dates 
# to use for the Date header of the email.
DATE_HEADER_ORDER = ('modified', 'issued', 'created')

# 1: Apply Q-P conversion (required for some MUAs).
# 0: Send message in 8-bits.
# http://cr.yp.to/smtp/8bitmime.html
QP_REQUIRED = 0

# 1: Name feeds as they're being processed.
# 0: Keep quiet.
VERBOSE = 0

# 1: Use the publisher's email if you can't find the author's.
# 0: Just use the DEFAULT_FROM email instead.
USE_PUBLISHER_EMAIL = 0

# 1: Use SMTP_SERVER to send mail.
# 0: Call /usr/sbin/sendmail to send mail.
SMTP_SEND = 0

SMTP_SERVER = "smtp.yourisp.net:25"
AUTHREQUIRED = 0 # if you need to use SMTP AUTH set to 1
SMTP_USER = 'username'  # for SMTP AUTH, set SMTP username here
SMTP_PASS = 'password'  # for SMTP AUTH, set SMTP password here

# Set this to add a bonus header to all emails (start with '\n').
BONUS_HEADER = ''
# Example: BONUS_HEADER = '\nApproved: joe@bob.org'

# Set this to override From addresses. Keys are feed URLs, values are new titles.
OVERRIDE_FROM = {}

# Set this to override the timeout (in seconds) for feed server response
FEED_TIMEOUT = 60

# Optional CSS styling
USE_CSS_STYLING = 0
STYLE_SHEET='h1 {font: 18pt Georgia, "Times New Roman";} body {font: 12pt Arial;} a:link {font: 12pt Arial; font-weight: bold; color: #0000cc} blockquote {font-family: monospace; }  .header { background: #e0ecff; border-bottom: solid 4px #c3d9ff; padding: 5px; margin-top: 0px; color: red;} .header a { font-size: 20px; text-decoration: none; } .footer { background: #c3d9ff; border-top: solid 4px #c3d9ff; padding: 5px; margin-bottom: 0px; } #entry {border: solid 4px #c3d9ff; } #body { margin-left: 5px; margin-right: 5px; }'

# If you have an HTTP Proxy set this in the format 'http://your.proxy.here:8080/'
PROXY=""

# To most correctly encode emails with international characters, we iterate through the list below and use the first character set that works
# Eventually (and theoretically) ISO-8859-1 and UTF-8 are our catch-all failsafes
CHARSET_LIST='US-ASCII', 'BIG5', 'ISO-2022-JP', 'ISO-8859-1', 'UTF-8'

from email.MIMEText import MIMEText
from email.Header import Header
from email.Utils import parseaddr, formataddr
			 
# Note: You can also override the send function.

def send(sender, recipient, subject, body, contenttype, extraheaders=None, smtpserver=None):
	"""Send an email.
	
	All arguments should be Unicode strings (plain ASCII works as well).
	
	Only the real name part of sender and recipient addresses may contain
	non-ASCII characters.
	
	The email will be properly MIME encoded and delivered though SMTP to
	localhost port 25.  This is easy to change if you want something different.
	
	The charset of the email will be the first one out of the list
	that can represent all the characters occurring in the email.
	"""

	# Header class is smart enough to try US-ASCII, then the charset we
	# provide, then fall back to UTF-8.
	header_charset = 'ISO-8859-1'
	
	# We must choose the body charset manually
	for body_charset in CHARSET_LIST:
	    try:
	        body.encode(body_charset)
	    except UnicodeError:
	        pass
	    else:
	        break

	# Split real name (which is optional) and email address parts
	sender_name, sender_addr = parseaddr(sender)
	recipient_name, recipient_addr = parseaddr(recipient)
	
	# We must always pass Unicode strings to Header, otherwise it will
	# use RFC 2047 encoding even on plain ASCII strings.
	sender_name = str(Header(unicode(sender_name), header_charset))
	recipient_name = str(Header(unicode(recipient_name), header_charset))
	
	# Make sure email addresses do not contain non-ASCII characters
	sender_addr = sender_addr.encode('ascii')
	recipient_addr = recipient_addr.encode('ascii')
	
	# Create the message ('plain' stands for Content-Type: text/plain)
	msg = MIMEText(body.encode(body_charset), contenttype, body_charset)
	msg['To'] = formataddr((recipient_name, recipient_addr))
	msg['Subject'] = Header(unicode(subject), header_charset)
	for hdr in extraheaders.keys():
		msg[hdr] = Header(unicode(extraheaders[hdr], header_charset))
		
	fromhdr = formataddr((sender_name, sender_addr))
	msg['From'] = fromhdr
		
	msg_as_string = msg.as_string()
	if QP_REQUIRED:
		ins, outs = SIO(msg_as_string), SIO()
		mimify.mimify(ins, outs)
		msg_as_string = outs.getvalue()
    		
	if SMTP_SEND:
		if not smtpserver: 
			import smtplib
			
			try:
				smtpserver = smtplib.SMTP(SMTP_SERVER)
			except KeyboardInterrupt:
				raise
			except Exception, e:
				print >>warn, ""
				print >>warn, ('Fatal error: could not connect to mail server "%s"' % SMTP_SERVER)
				if hasattr(e, 'reason'):
					print >>warn, "Reason:", e.reason
				sys.exit(1)
					
			if AUTHREQUIRED:
				try:
					smtpserver.ehlo()
					smtpserver.starttls()
					smtpserver.ehlo()
					smtpserver.login(SMTP_USER, SMTP_PASS)
				except KeyboardInterrupt:
					raise
				except Exception, e:
					print >>warn, ""
					print >>warn, ('Fatal error: could not authenticate with mail server "%s" as user "%s"' % (SMTP_SERVER, SMTP_USER))
					if hasattr(e, 'reason'):
						print >>warn, "Reason:", e.reason
					sys.exit(1)
					
		smtpserver.sendmail(sender, recipient, msg_as_string)
		return smtpserver

	else:
		i, o = os.popen2(["/usr/sbin/sendmail", recipient])
		i.write(msg_as_string)
		i.close(); o.close()
		del i, o
		return None

## html2text options ##

# Use Unicode characters instead of their ascii psuedo-replacements
UNICODE_SNOB = 0

# Put the links after each paragraph instead of at the end.
LINKS_EACH_PARAGRAPH = 0

# Wrap long lines at position. 0 for no wrapping. (Requires Python 2.3.)
BODY_WIDTH = 0

### Load the Options ###

# Read options from config file if present.
import sys
sys.path.append(".")
try:
	from config import *
except:
	pass
	
### Import Modules ###

import cPickle as pickle, md5, time, os, traceback, urllib2, sys, types
unix = 0
try:
	import fcntl
	unix = 1
except:
	pass
		
import socket; socket_errors = []
for e in ['error', 'gaierror']:
	if hasattr(socket, e): socket_errors.append(getattr(socket, e))
import mimify; from StringIO import StringIO as SIO; mimify.CHARSET = 'utf-8'

import feedparser
feedparser.USER_AGENT = "rss2email/"+__version__+ " +http://www.aaronsw.com/2002/rss2email/"

import html2text as h2t

h2t.UNICODE_SNOB = UNICODE_SNOB
h2t.LINKS_EACH_PARAGRAPH = LINKS_EACH_PARAGRAPH
h2t.BODY_WIDTH = BODY_WIDTH
html2text = h2t.html2text

### Utility Functions ###

import threading
class TimeoutError(Exception): pass

class InputError(Exception): pass

def timelimit(timeout, function):
#    def internal(function):
        def internal2(*args, **kw):
            """
            from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/473878
            """
            class Calculator(threading.Thread):
                def __init__(self):
                    threading.Thread.__init__(self)
                    self.result = None
                    self.error = None
                
                def run(self):
                    try:
                        self.result = function(*args, **kw)
                    except:
                        self.error = sys.exc_info()
            
            c = Calculator()
            c.setDaemon(True) # don't hold up exiting
            c.start()
            c.join(timeout)
            if c.isAlive():
                raise TimeoutError
            if c.error:
                raise c.error[0], c.error[1]
            return c.result
        return internal2
#    return internal
    

warn = sys.stderr

def isstr(f): return isinstance(f, type('')) or isinstance(f, type(u''))
def ishtml(t): return type(t) is type(())
def contains(a,b): return a.find(b) != -1
def unu(s): # I / freakin' hate / that unicode
	if type(s) is types.UnicodeType: return s.encode('utf-8')
	else: return s

def quote822(s):
	"""Quote names in email according to RFC822."""
	return '"' + unu(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

def header7bit(s):
	"""QP_CORRUPT headers."""
	#return mimify.mime_encode_header(s + ' ')[:-1]
	# XXX due to mime_encode_header bug
	import re
	p = re.compile('=\n([^ \t])');
	return p.sub(r'\1', mimify.mime_encode_header(s + ' ')[:-1])

### Parsing Utilities ###

def getContent(entry, HTMLOK=0):
	"""Select the best content from an entry, deHTMLizing if necessary.
	If raw HTML is best, an ('HTML', best) tuple is returned. """
	
	# How this works:
	#  * We have a bunch of potential contents. 
	#  * We go thru looking for our first choice. 
	#    (HTML or text, depending on HTMLOK)
	#  * If that doesn't work, we go thru looking for our second choice.
	#  * If that still doesn't work, we just take the first one.
	#
	# Possible future improvement:
	#  * Instead of just taking the first one
	#    pick the one in the "best" language.
	#  * HACK: hardcoded HTMLOK, should take a tuple of media types
	
	conts = entry.get('content', [])
	
	if entry.get('summary_detail', {}):
		conts += [entry.summary_detail]
	
	if conts:
		if HTMLOK:
			for c in conts:
				if contains(c.type, 'html'): return ('HTML', c.value)
	
		if not HTMLOK: # Only need to convert to text if HTML isn't OK
			for c in conts:
				if contains(c.type, 'html'):
					return html2text(c.value)
		
		for c in conts:
			if c.type == 'text/plain': return c.value
	
		return conts[0].value	
	
	return ""

def getID(entry):
	"""Get best ID from an entry."""
	if TRUST_GUID:
		if 'id' in entry and entry.id: return entry.id

	content = getContent(entry)
	if content and content != "\n": return md5.new(unu(content)).hexdigest()
	if 'link' in entry: return entry.link
	if 'title' in entry: return md5.new(unu(entry.title)).hexdigest()

def getName(r, entry):
	"""Get the best name."""

	feed = r.feed
	if hasattr(r, "url") and r.url in OVERRIDE_FROM.keys():
		return OVERRIDE_FROM[r.url]
	
	name = feed.get('title', '')

	if 'name' in entry.get('author_detail', []): # normally {} but py2.1
		if entry.author_detail.name:
			if name: name += ": "
			det=entry.author_detail.name
			try:
			    name +=  entry.author_detail.name
			except UnicodeDecodeError:
			    name +=  unicode(entry.author_detail.name, 'utf-8')

	elif 'name' in feed.get('author_detail', []):
		if feed.author_detail.name:
			if name: name += ", "
			name += feed.author_detail.name
	
	return name

def getEmail(feed, entry):
	"""Get the best email_address."""

	if FORCE_FROM: return DEFAULT_FROM
	
	if 'email' in entry.get('author_detail', []):
		return entry.author_detail.email
	
	if 'email' in feed.get('author_detail', []):
		return feed.author_detail.email
		
	#TODO: contributors
	
	if USE_PUBLISHER_EMAIL:
		if 'email' in feed.get('publisher_detail', []):
			return feed.publisher_detail.email
		
		if feed.get("errorreportsto", ''):
			return feed.errorreportsto
			
	return DEFAULT_FROM

### Simple Database of Feeds ###

class Feed:
	def __init__(self, url, to):
		self.url, self.etag, self.modified, self.seen = url, None, None, {}
		self.to = to		

def load(lock=1):
	if not os.path.exists(feedfile):
		print 'Feedfile "%s" does not exist.  If you\'re using r2e for the first time, you' % feedfile
		print "have to run 'r2e new' first."
		sys.exit(1)
	try:
		feedfileObject = open(feedfile, 'r')
	except IOError, e:
		print "Feedfile could not be opened: %s" % e
		sys.exit(1)
	feeds = pickle.load(feedfileObject)
	if lock:
		if unix: fcntl.flock(feedfileObject.fileno(), fcntl.LOCK_EX)
		#HACK: to deal with lock caching
		feedfileObject = open(feedfile, 'r')
		feeds = pickle.load(feedfileObject)
		if unix: fcntl.flock(feedfileObject.fileno(), fcntl.LOCK_EX)

	return feeds, feedfileObject

def unlock(feeds, feedfileObject):
	if not unix: 
		pickle.dump(feeds, open(feedfile, 'w'))
	else:	
		pickle.dump(feeds, open(feedfile+'.tmp', 'w'))
		os.rename(feedfile+'.tmp', feedfile)
		fcntl.flock(feedfileObject.fileno(), fcntl.LOCK_UN)

#@timelimit(FEED_TIMEOUT)		
def parse(url, etag, modified):
	if PROXY == '':
		return feedparser.parse(url, etag, modified)
	else:
		proxy = urllib2.ProxyHandler( {"http":PROXY} )
		return feedparser.parse(url, etag, modified, handlers = [proxy])	
	
		
### Program Functions ###

def add(*args):
	if len(args) == 2 and contains(args[1], '@') and not contains(args[1], '://'):
		urls, to = [args[0]], args[1]
	else:
		urls, to = args, None
	
	feeds, feedfileObject = load()
	if (feeds and not isstr(feeds[0]) and to is None) or (not len(feeds) and to is None):
		print "No email address has been defined. Please run 'r2e email emailaddress' or"
		print "'r2e add url emailaddress'."
		sys.exit(1)
	for url in urls: feeds.append(Feed(url, to))
	unlock(feeds, feedfileObject)

def run(num=None):
	feeds, feedfileObject = load()
	try:
		# We store the default to address as the first item in the feeds list.
		# Here we take it out and save it for later.
		default_to = ""
		if feeds and isstr(feeds[0]): default_to = feeds[0]; ifeeds = feeds[1:] 
		else: ifeeds = feeds
		
		if num: ifeeds = [feeds[num]]
		
		smtpserver = None
		
		for f in ifeeds:
			try: 
				if VERBOSE: print >>warn, "I: Processing", f.url
				r = {}
				try:
					r = timelimit(FEED_TIMEOUT, parse)(f.url, f.etag, f.modified)
				except TimeoutError:
					print >>warn, 'W: feed "%s" timed out' % f.url
					continue
				
				# Handle various status conditions, as required
				if 'status' in r:
					if r.status == 301: f.url = r['url']
					elif r.status == 410:
						print >>warn, "W: feed gone; deleting", f.url
						feeds.remove(f)
						continue
				
				http_status = r.get('status', 200)
				http_headers = r.get('headers', {
				  'content-type': 'application/rss+xml', 
				  'content-length':'1'})
				exc_type = r.get("bozo_exception", Exception()).__class__
				if http_status != 304 and not r.get('version', ''):
					if http_status not in [200, 302]: 
						print >>warn, "W: error", http_status, f.url

					elif contains(http_headers.get('content-type', 'rss'), 'html'):
						print >>warn, "W: looks like HTML", f.url

					elif http_headers.get('content-length', '1') == '0':
						print >>warn, "W: empty page", f.url

					elif hasattr(socket, 'timeout') and exc_type == socket.timeout:
						print >>warn, "W: timed out on", f.url
					
					elif exc_type == IOError:
						print >>warn, "W:", r.bozo_exception, f.url
					
					elif hasattr(feedparser, 'zlib') and exc_type == feedparser.zlib.error:
						print >>warn, "W: broken compression", f.url
					
					elif exc_type in socket_errors:
						exc_reason = r.bozo_exception.args[1]
						print >>warn, "W:", exc_reason, f.url

					elif exc_type == urllib2.URLError:
						if r.bozo_exception.reason.__class__ in socket_errors:
							exc_reason = r.bozo_exception.reason.args[1]
						else:
							exc_reason = r.bozo_exception.reason
						print >>warn, "W:", exc_reason, f.url
					
					elif exc_type == AttributeError:
						print >>warn, "W:", r.bozo_exception, f.url
					
					elif exc_type == KeyboardInterrupt:
						raise r.bozo_exception
						
					elif r.bozo:
						print >>warn, 'E: error in "%s" feed (%s)' % (f.url, r.get("bozo_exception", "can't process"))

					else:
						print >>warn, "=== SEND THE FOLLOWING TO rss2email@aaronsw.com ==="
						print >>warn, "E:", r.get("bozo_exception", "can't process"), f.url
						print >>warn, r
						print >>warn, "rss2email", __version__
						print >>warn, "feedparser", feedparser.__version__
						print >>warn, "html2text", h2t.__version__
						print >>warn, "Python", sys.version
						print >>warn, "=== END HERE ==="
					continue
				
				r.entries.reverse()
				
				for entry in r.entries:
					id = getID(entry)
					
					# If TRUST_GUID isn't set, we get back hashes of the content.
					# Instead of letting these run wild, we put them in context
					# by associating them with the actual ID (if it exists).
					
					frameid = entry.get('id', id)
					
					# If this item's ID is in our database
					# then it's already been sent
					# and we don't need to do anything more.
					
					if f.seen.has_key(frameid) and f.seen[frameid] == id: continue

					if not (f.to or default_to):
						print "No default email address defined. Please run 'r2e email emailaddress'"
						print "Ignoring feed %s" % f.url
						break
					
					if 'title_detail' in entry and entry.title_detail:
						title = entry.title_detail.value
						if contains(entry.title_detail.type, 'html'):
							title = html2text(title)
					else:
						title = getContent(entry)[:70]

					title = title.replace("\n", " ").strip()
					
					datetime = time.gmtime()

					if DATE_HEADER:
						for datetype in DATE_HEADER_ORDER:
							kind = datetype+"_parsed"
							if kind in entry and entry[kind]: datetime = entry[kind]
						
					link = entry.get('link', "")
					
					from_addr = getEmail(r.feed, entry)
					
					name = getName(r, entry)
					fromhdr = '"'+ name + '" <' + from_addr + ">"
					tohdr = (f.to or default_to)
					subjecthdr = title
					datehdr = time.strftime("%a, %d %b %Y %H:%M:%S -0000", datetime)
					useragenthdr = "rss2email"
					extraheaders = {'Date': datehdr, 'User-Agent': useragenthdr}
					if BONUS_HEADER != '':
						for hdr in BONUS_HEADER.strip().splitlines():
							pos = hdr.strip().find(':')
							if pos > 0:
								extraheaders[hdr[:pos]] = hdr[pos+1:].strip()
							else:
								print >>warn, "W: malformed BONUS HEADER", BONUS_HEADER	
					
					entrycontent = getContent(entry, HTMLOK=HTML_MAIL)
					contenttype = 'plain'
					content = ''
					if USE_CSS_STYLING and HTML_MAIL:
						contenttype = 'html'
						content = "<html>\n" 
						content += '<head><style><!--' + STYLE_SHEET + '//--></style></head>\n'
						content += '<body>\n'
						content += '<div id="entry">\n'
						content += '<h1'
						content += ' class="header"'
						content += '><a href="'+link+'">'+subjecthdr+'</a></h1>\n\n'
						if ishtml(entrycontent):
							body = entrycontent[1].strip()
						else:
							body = entrycontent.strip()
						if body != '':	
							content += '<div id="body"><table><tr><td>\n' + body + '</td></tr></table></div>\n'
						content += '\n<p class="footer">URL: <a href="'+link+'">'+link+'</a>'
						if hasattr(entry,'enclosures'):
							for enclosure in entry.enclosures:
								if enclosure.url != "":
									content += ('<br/>Enclosure: <a href="'+unu(enclosure.url)+'">'+unu(enclosure.url)+"</a>\n")
						content += '</p></div>\n'
						content += "\n\n</body></html>"
					else:	
						if ishtml(entrycontent):
							contenttype = 'html'
							content = "<html>\n" 
							content = ("<html><body>\n\n" + 
							           '<h1><a href="'+link+'">'+subjecthdr+'</a></h1>\n\n' +
							           entrycontent[1].strip() + # drop type tag (HACK: bad abstraction)
							           '<p>URL: <a href="'+link+'">'+link+'</a></p>' )
							           
							if hasattr(entry,'enclosures'):
								for enclosure in entry.enclosures:
									if enclosure.url != "":
										content += ('Enclosure: <a href="'+unu(enclosure.url)+'">'+unu(enclosure.url)+"</a><br/>\n")
							
							content += ("\n</body></html>")
						else:
							content = entrycontent.strip() + "\n\nURL: "+link
							if hasattr(entry,'enclosures'):
								for enclosure in entry.enclosures:
									if enclosure.url != "":
										content += ('\nEnclosure: '+unu(enclosure.url)+"\n")

					smtpserver = send(fromhdr, tohdr, subjecthdr, content, contenttype, extraheaders, smtpserver)
			
					f.seen[frameid] = id
					
				f.etag, f.modified = r.get('etag', None), r.get('modified', None)
			except (KeyboardInterrupt, SystemExit):
				raise
			except:
				print >>warn, "=== SEND THE FOLLOWING TO rss2email@aaronsw.com ==="
				print >>warn, "E: could not parse", f.url
				traceback.print_exc(file=warn)
				print >>warn, "rss2email", __version__
				print >>warn, "feedparser", feedparser.__version__
				print >>warn, "html2text", h2t.__version__
				print >>warn, "Python", sys.version
				print >>warn, "=== END HERE ==="
				continue

	finally:		
		unlock(feeds, feedfileObject)
		if smtpserver:
			smtpserver.quit()

def list():
	feeds, feedfileObject = load(lock=0)
	default_to = ""
	
	if feeds and isstr(feeds[0]):
		default_to = feeds[0]; ifeeds = feeds[1:]; i=1
		print "default email:", default_to
	else: ifeeds = feeds; i = 0
	for f in ifeeds:
		print `i`+':', f.url, '('+(f.to or ('default: '+default_to))+')'
		if not (f.to or default_to):
			print "   W: Please define a default address with 'r2e email emailaddress'"
		i+= 1

def delete(n):
	feeds, feedfileObject = load()
	if (n == 0) and (feeds and isstr(feeds[0])):
		print >>warn, "W: ID has to be equal to or higher than 1"
	elif n >= len(feeds):
		print >>warn, "W: no such feed"
	else:
		print >>warn, "W: deleting feed %s" % feeds[n].url
		feeds = feeds[:n] + feeds[n+1:]
		if n != len(feeds):
			print >>warn, "W: feed IDs have changed, list before deleting again"
	unlock(feeds, feedfileObject)
	
def email(addr):
	feeds, feedfileObject = load()
	if feeds and isstr(feeds[0]): feeds[0] = addr
	else: feeds = [addr] + feeds
	unlock(feeds, feedfileObject)

if __name__ == '__main__':
	args = sys.argv
	try:
		if len(args) < 3: raise InputError, "insufficient args"
		feedfile, action, args = args[1], args[2], args[3:]
		
		if action == "run": 
			if args and args[0] == "--no-send":
				def send(sender, recipient, subject, body, contenttype, extraheaders=None, smtpserver=None):
					if VERBOSE: print 'Not sending:', unu(subject)

			if args and args[-1].isdigit(): run(int(args[-1]))
			else: run()

		elif action == "email":
			if not args:
				raise InputError, "Action '%s' requires an argument" % action
			else:
				email(args[0])

		elif action == "add": add(*args)

		elif action == "new": 
			if len(args) == 1: d = [args[0]]
			else: d = []
			pickle.dump(d, open(feedfile, 'w'))

		elif action == "list": list()

		elif action in ("help", "--help", "-h"): print __doc__

		elif action == "delete":
			if not args:
				raise InputError, "Action '%s' requires an argument" % action
			elif args[0].isdigit():
				delete(int(args[0]))
			else:
				raise InputError, "Action '%s' requires a number as its argument" % action

		else:
			raise InputError, "Invalid action"
		
	except InputError, e:
		print "E:", e
		print
		print __doc__



