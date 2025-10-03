#!/usr/bin/env python3

import rss2email.command
import rss2email.config
import rss2email.email
import rss2email.error
import rss2email.feed
import rss2email.feeds
import rss2email.post_process
import rss2email.util

import doctest


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(rss2email.command))
    tests.addTests(doctest.DocTestSuite(rss2email.config))
    tests.addTests(doctest.DocTestSuite(rss2email.email))
    tests.addTests(doctest.DocTestSuite(rss2email.error))
    tests.addTests(doctest.DocTestSuite(rss2email.feed))
    tests.addTests(doctest.DocTestSuite(rss2email.feeds))
    tests.addTests(doctest.DocTestSuite(rss2email.post_process))
    tests.addTests(doctest.DocTestSuite(rss2email.util))
    return tests


if __name__ == "__main__":
    import unittest

    unittest.main()
