# -*- coding: utf-8 -*-
"""Unit tests for rss2email.

These tests make sure that rss2email works as it should. If you
find a bug, the best way to express it is as a test
case like this that fails."""

import unittest
from rss2email import *
import rss2email
import feedparser

class test_validateEmail(unittest.TestCase):
	""""""
	def test_valid_email(self):
		email = validateEmail("valid@example.com", "planb@example.com")
		self.assertEqual(email, "valid@example.com")

	def test_no_mail_server(self):
		email = validateEmail("invalid", "planb@example.com")
		self.assertEqual(email, "planb@example.com")

	def test_no_email_name(self):
		email = validateEmail("@invalid", "planb@example.com")
		self.assertEqual(email, "planb@example.com")

	def test_no_at(self):
		email = validateEmail("invalid", "planb@example.com")
		self.assertEqual(email, "planb@example.com")

class test_getName(unittest.TestCase):
    """"""
    def setUp(self):
        self.feed = feedparser.parse("""
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <author>
    <name>Example author</name>
    <email>me@example.com</email>
    <url>http://example.com/</url>
  </author>
</entry>
</feed>
        """)
        self.entry = self.feed.entries[0]


    def test_no_friendly_name(self):
        rss2email.NO_FRIENDLY_NAME = 1
        name = getName(0, 0)
        rss2email.NO_FRIENDLY_NAME = 0
        self.assertEqual(name, '')
        
    def test_override_from(self):
        # have to fake url attribute because it is only set on downloaded feeds
        urlToOverride = 'http://example.com/feed/'
        self.feed['url'] = urlToOverride
        rss2email.OVERRIDE_FROM = {urlToOverride:'override'}
        name = getName(self.feed, self.entry)
        self.assertEqual(name, 'override')

    def test_no_friendly_name_negative(self):
        rss2email.NO_FRIENDLY_NAME = 0
        name=getName(self.feed, self.entry)
        self.assertEqual(name, 'Example author')

class test_getTags(unittest.TestCase):
    """"""
    def test_valid_tags(self):
        entry = {'tags': [{'term': u'tag1', 'scheme': None, 'label': None}]}
        tagline = getTags(entry)
        self.assertEqual(tagline, "tag1")

    def test_no_tags(self):
        entry = {}
        tagline = getTags(entry)
        self.assertEqual(tagline, "")

    def test_empty_tags(self):
        entry = {'tags': []}
        tagline = getTags(entry)
        self.assertEqual(tagline, "")

    def test_no_term(self):
        entry = {'tags': [{'scheme': None, 'label': None}]}
        tagline = getTags(entry)
        self.assertEqual(tagline, "")

    def test_empty_term(self):
        entry = {'tags': [{'term': u'', 'scheme': None, 'label': None}]}
        tagline = getTags(entry)
        self.assertEqual(tagline, "")

    def test_multiple_tags(self):
        entry = {'tags': [{'term': u'tag1', 'scheme': None, 'label': None}, {'term': u'tag2', 'scheme': None, 'label': None}]}
        tagline = getTags(entry)
        self.assertEqual(tagline, "tag1,tag2")

    

if __name__ == '__main__':
    unittest.main()

