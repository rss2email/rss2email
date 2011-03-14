# -*- coding: utf-8 -*-
"""Unit tests for rss2email.

These tests make sure that rss2email works as it should. If you
find a bug, the best way to express it is as a test
case like this that fails."""

import unittest
from rss2email import *

class Test_validateEmail(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
