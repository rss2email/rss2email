#!/usr/bin/python
"""rss2email: get RSS feeds emailed to you
http://www.aaronsw.com/2002/rss2email

Usage: python rss2email.py feedfile action [options]
  feedfile: name of the file to store feed info in
  action [options]:
	new [youremail] (create new feedfile)
	email [yournewemail] (update default email)
	run [--no-send]
	add feedurl [youremail]
	list
	delete n
"""
__version__ = "2.28"
__author__ = "Aaron Swartz (me@aaronsw.com)"
__copyright__ = "(C) 2004 Aaron Swartz. GNU GPL 2."
___contributors__ = ["Dean Jackson (dino@grorg.org)", 
					 "Brian Lalor (blalor@ithacabands.org)",
					 "Joey Hess", 'Matej Cepl']

### Vaguely Customizable Options ###

# The email address messages are from by default:
DEFAULT_FROM = "bozo@dev.null"

# 1: Only use the DEFAULT_FROM address.
# 0: Use the email address specified by the feed, when possible.
FORCE_FROM = 0

# 1: Receive one email per post
# 0: Receive an email every time a post changes
TRUST_GUID = 1

# 1: Generate Date header based on item's date, when possible
# 0: Generate Date header based on time sent
DATE_HEADER = 0

# 1: Treat the contents of <description> as HTML
# 0: Send the contents of <description> as is, without conversion
TREAT_DESCRIPTION_AS_HTML = 1

# 1: Apply Q-P conversion (required for some MUAs)
# 0: Send message in 8-bits
# http://cr.yp.to/smtp/8bitmime.html
QP_REQUIRED = 0

# 1: Name feeds as they're being processed.
# 0: Keep quiet.
VERBOSE = 0

def send(fr, to, message):
	i, o = os.popen2(["/usr/sbin/sendmail", to])
	i.write(message)
	i.close(); o.close()
	del i, o
	
# def send(fr, to, message):
# 	import smtplib
# 	s = smtplib.SMTP("vorpal.notabug.com:26")
# 	s.sendmail(fr, [to], message)

### End of Options ###

# Read options from config file if present.
import sys
sys.path.append(".")
try:
	from config import *
except:
	pass

from html2text import html2text, expandEntities
import feedparser
import cPickle as pickle, fcntl, md5, time, os, traceback
if QP_REQUIRED: import mimify; from StringIO import StringIO as SIO
def isstr(f): return isinstance(f, type('')) or isinstance(f, type(u''))

def e(obj, val):
	x = expandEntities(obj[val])
	if type(x) is unicode: x = x.encode('utf-8')
	return x.strip()

def quoteEmailName(s):
	return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

def getContent(item, url):
	if item.has_key('content') and item['content']:
		for c in item['content']:
			if c['type'] == 'text/plain': return c['value']

		for c in item['content']:
			if c['type'].find('html') != -1:
				return html2text(c['value'], c['base'])
		
		return item['content'][0]['value']
			
	if item.has_key('description'): 
		if TREAT_DESCRIPTION_AS_HTML:
			return html2text(item['description'], url)
		else:
			return item['description']
	
	if item.has_key('summary'): return item['summary']
	return ""

def getID(item, content):
	if TRUST_GUID:
		if item.has_key('id') and item['id']: return item['id']

	if content: return md5.new(content).hexdigest()
	if item.has_key('link'): return item['link']
	if item.has_key('title'): return md5.new(item['title']).hexdigest()

class Feed:
	def __init__(self, url, to):
		self.url, self.etag, self.modified, self.seen = url, None, None, {}
		self.to = to		

def load(lock=1):
	ff2 = open(feedfile, 'r')
	feeds = pickle.load(ff2)
	if lock: fcntl.flock(ff2, fcntl.LOCK_EX)
	return feeds, ff2

def unlock(feeds, ff2):
	pickle.dump(feeds, open(feedfile, 'w'))
	fcntl.flock(ff2, fcntl.LOCK_UN)
	
def add(url, to=None):
	feeds, ff2 = load()
	if not isstr(feeds[0]) and to is None:
		raise 'NoEmail', "Run `email newaddr` or `add url addr`."
	feeds.append(Feed(url, to))
	unlock(feeds, ff2)

def run():
	feeds, ff2 = load()

	if isstr(feeds[0]): default_to = feeds[0]; ifeeds = feeds[1:]
	else: ifeeds = feeds
	
	for f in ifeeds:
		if VERBOSE: print "Processing", f.url
		try: result = feedparser.parse(f.url, f.etag, f.modified)
		except:
			print "E: could not parse", f.url
			traceback.print_exc()
			continue
		
		if result.has_key('status') and result['status'] == 301: f.url = result['url']
		
		if result.has_key('encoding'): enc = result['encoding']
		else: enc = 'utf-8'
		
		c, ert = result['channel'], 'errorreportsto'
		
		headers = "From: "
		if c.has_key('title'): headers += quoteEmailName(e(c, 'title')) + ' '
		if FORCE_FROM and c.has_key(ert) and c[ert].startswith('mailto:'):
			fr = c[ert][7:]
		else:
			fr = DEFAULT_FROM
		
		headers += '<'+fr+'>'
				
		headers += "\nTo: " + (f.to or default_to) # set a default email!
		if not QP_REQUIRED:
			headers += '\nContent-Type: text/plain; charset="' + enc + '"'
		
		if not result['items'] and ((not result.has_key('status') or (result.has_key('status') and result['status'] != 304))):
			print "W: no items; invalid feed? (" + f.url + ")"
			continue
	
		for i in result['items']:
			content = getContent(i, f.url)
			id = getID(i, content)
		
			if i.has_key('link') and i['link']: frameid = link = e(i, 'link')
			else: frameid = id; link = None
			
			if f.seen.has_key(frameid) and f.seen[frameid] == id:
				continue # have seen
	
			if i.has_key('title'): title = e(i, 'title')
			else: title = content[:70].replace("\n", " ")
			
			if DATE_HEADER and i.has_key('date_parsed'):
				datetime = i['date_parsed']	
			else:
				datetime = time.gmtime()
			
			message = (headers
					   + "\nSubject: " + title
					   + "\nDate: " + time.strftime("%a, %d %b %Y %H:%M:%S -0000", datetime)
					   + "\nUser-Agent: rss2email"
					   + "\n")
			
			message += "\n" + content.strip() + "\n"
			
			if link: message += "\nURL: " + link + "\n"
			
			if QP_REQUIRED:
				mimify.CHARSET = enc
				ins, outs = SIO(message), SIO()
				mimify.mimify(ins, outs); outs.seek(0)
				message = outs.read()
			
			send(fr, (f.to or default_to), message)
	
			f.seen[frameid] = id
			
		f.etag, f.modified = result.get('etag', None), result.get('modified', None)
	
	unlock(feeds, ff2)

def list():
	feeds, ff2 = load(lock=0)
	
	if isstr(feeds[0]):
		default_to = feeds[0]; ifeeds = feeds[1:]; i=1
		print "default email:", default_to
	else: ifeeds = feeds; i = 0
	for f in ifeeds:
		print `i`+':', f.url, '('+(f.to or ('default: '+default_to))+')'
		i+= 1

def delete(n):
	feeds, ff2 = load()
	feeds = feeds[:n] + feeds[n+1:]
	unlock(feeds, ff2)
	
def email(addr):
	feeds, ff2 = load()
	if isstr(feeds[0]): feeds[0] = addr
	else: feeds = [addr] + feeds
	unlock(feeds, ff2)

if __name__ == '__main__':
	ie, args = "InputError", sys.argv
	try:
		if len(args) < 3: raise ie, "insufficient args"
		feedfile, action, args = args[1], args[2], args[3:]
		
		if action == "run": 
			if args and args[0] == "--no-send":
				def send(x,y,z):
					if VERBOSE: print 'Not sending', (
					[x for x in z.splitlines() if x.startswith("Subject:")][0])
			run()

		elif action == "email":
			email(args[0])
			print "W: Feed IDs may have changed. Run `list` before `delete`."

		elif action == "add": add(*args)

		elif action == "new": 
			if len(args) == 1: d = [args[0]]
			else: d = []
			pickle.dump(d, open(feedfile, 'w'))

		elif action == "list": list()

		elif action == "delete": delete(int(args[0]))

		else:
			raise ie, "invalid action"
			
	except ie, e:
		print "E:", e
		print
		print __doc__