#!/usr/bin/env python3

"""Test processing logic on known feeds.
"""

import difflib as _difflib
import glob as _glob
import io as _io
import logging as _logging
import os as _os
import re as _re
import sys
import tempfile
import multiprocessing
from parameterized import parameterized
import subprocess
import unittest
import mailbox
import http.server
import time

top_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, top_dir)
_os.environ['PYTHONPATH'] = top_dir + ":" + _os.environ['PYTHONPATH']

import rss2email as _rss2email
import rss2email.config as _rss2email_config
import rss2email.feed as _rss2email_feed


def find_email_tests():
    this_dir = _os.path.dirname(__file__)
    tests = []
    for dirpath, dirnames, filenames in _os.walk(this_dir):
        filenames.sort()
        for filename in filenames:
            if filename.endswith('.config'):
                tests.append(_os.path.relpath(_os.path.join(dirpath, filename),
                                              start=this_dir))
    return tests


class TestEmails(unittest.TestCase):
    class Send (list):
        def __call__(self, sender, message):
            self.append((sender, message))

        def as_string(self):
            chunks = [
                'SENT BY: {}\n{}\n'.format(sender, message.as_string())
                for sender,message in self]
            return '\n'.join(chunks)

    def __init__(self, *args, **kwargs):
        super(TestEmails, self).__init__(*args, **kwargs)

        # Get a copy of the internal rss2email.CONFIG for copying
        _stringio = _io.StringIO()
        _rss2email_config.CONFIG.write(_stringio)
        self.BASE_CONFIG_STRING = _stringio.getvalue()
        del _stringio

        self.MESSAGE_ID_REGEXP = _re.compile(
            '^Message-ID: <[^@]*@dev.null.invalid>$', _re.MULTILINE)
        self.USER_AGENT_REGEXP = _re.compile(
            r'^User-Agent: rss2email/[0-9.]* \(https:\S*\)$', _re.MULTILINE)
        self.BOUNDARY_REGEXP = _re.compile('===============[^=]+==')

    def clean_result(self, text):
        """Cleanup dynamic portions of the generated email headers

        >>> text = (
        ...      'Content-Type: multipart/digest;\\n'
        ...      '  boundary="===============7509425281347501533=="\\n'
        ...      'MIME-Version: 1.0\\n'
        ...      'Date: Tue, 23 Aug 2011 15:57:37 -0000\\n'
        ...      'Message-ID: <9dff03db-f5a7@dev.null.invalid>\\n'
        ...      'User-Agent: rss2email/3.5 (https://github.com/rss2email/rss2email)\\n'
        ...      )
        >>> print(clean_result(text).rstrip())
        Content-Type: multipart/digest;
        boundary="===============...=="
        MIME-Version: 1.0
        Date: Tue, 23 Aug 2011 15:57:37 -0000
        Message-ID: <...@dev.null.invalid>
        User-Agent: rss2email/...
        """
        for regexp,replacement in [
                (self.MESSAGE_ID_REGEXP, 'Message-ID: <...@dev.null.invalid>'),
                (self.USER_AGENT_REGEXP, 'User-Agent: rss2email/...'),
                (self.BOUNDARY_REGEXP, '===============...=='),
        ]:
            text = regexp.sub(replacement, text)
        return text

    @parameterized.expand(((p) for p in find_email_tests()))
    def test_send(self, config_path, force=False):
        with ExecContext():
            dirname = _os.path.dirname(config_path)
            feed_path = _glob.glob(_os.path.join(dirname, 'feed.*'))[0]

            _rss2email.LOG.info('testing {}'.format(config_path))
            config = _rss2email_config.Config()
            config.read_string(self.BASE_CONFIG_STRING)
            read_paths = config.read([config_path])
            feed = _rss2email_feed.Feed(name='test', url=feed_path,
                                        config=config)
            expected_path = config_path.replace('config', 'expected')
            with open(expected_path, 'r') as f:
                expected = self.clean_result(f.read())
            feed._send = TestEmails.Send()
            feed.run()
            generated = feed._send.as_string()
            if force:
                with open(expected_path, 'w') as f:
                    f.write(generated)
            generated = self.clean_result(generated)
            if generated != expected:
                diff_lines = _difflib.unified_diff(
                    expected.splitlines(), generated.splitlines(),
                    'expected', 'generated', lineterm='')
                raise ValueError(
                    'error processing {}\n{}'.format(
                        config_path,
                        '\n'.join(diff_lines)))


class ExecContext:
    """Creates temporary config, data file and lets you call r2e with them
    easily. Cleans up temp files afterwards.

    Example:

    with ExecContext(config="[DEFAULT]\nto=me@example.com") as context:
        context.call("run", "--no-send")

    """
    def __init__(self, config=None):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = _os.path.join(self.tmpdir, "rss2email.cfg")
        self.data_path = _os.path.join(self.tmpdir, "rss2email.json")

        if config:
            with open(self.cfg_path, "w") as f:
                f.write(config)

    def __enter__(self):
        test_dir = _os.path.dirname(__file__)
        self.orig_dir = _os.getcwd()
        _os.chdir(test_dir)
        return self

    def __exit__(self, type, value, traceback):
        try:
            if _os.path.exists(self.cfg_path):
                _os.remove(self.cfg_path)
            if _os.path.exists(self.data_path):
                _os.remove(self.data_path)
            _os.rmdir(self.tmpdir)
        finally:
            _os.chdir(self.orig_dir)

    def call(self, *args):
        subprocess.call(["r2e", "-c", self.cfg_path, "-d", self.data_path] + list(args))

class NoLogHandler(http.server.SimpleHTTPRequestHandler):
    "No-op handler for http.server"
    def log_message(self, format, *args):
        return

class TestFetch(unittest.TestCase):
    "Retrieving feeds from servers"
    def test_delay(self):
        "Waits before fetching repeatedly from the same server"
        wait_time = 0.3
        delay_cfg = """[DEFAULT]
        to = example@example.com
        same-server-fetch-interval = {}
        """.format(wait_time)

        num_requests = 3

        def webserver(queue):
            httpd = http.server.HTTPServer(('', 0), NoLogHandler)
            try:
                port = httpd.server_address[1]
                queue.put(port)

                start = 0
                for _ in range(num_requests):
                    httpd.handle_request()
                    end = time.time()
                    if end - start < wait_time:
                        queue.put("too fast")
                        return
                    start = end
                queue.put("ok")
            finally:
                httpd.server_close()

        with ExecContext(delay_cfg) as ctx:
            queue = multiprocessing.Queue()
            webserver_proc = multiprocessing.Process(
                target=webserver, args=(queue,))
            webserver_proc.start()
            port = queue.get()

            for i in range(num_requests):
                ctx.call("add", 'test{i}'.format(i = i), 'http://127.0.0.1:{port}/disqus/feed.rss'.format(port = port))
            ctx.call("run", "--no-send")

        result = queue.get()

        if result == "too fast":
            raise Exception("r2e did not delay long enough!")

class TestSend(unittest.TestCase):
    "Send email using the various email-protocol choices"
    def setUp(self):
        "Starts web server to serve feeds"
        def webserver(queue):
            httpd = http.server.HTTPServer(('', 0), NoLogHandler)
            try:
                port = httpd.server_address[1]
                queue.put(port)

                # to make the web server serve your request, you have
                # to put something into the queue to advance this loop
                while queue.get() != "stop":
                    httpd.handle_request()
            finally:
                httpd.server_close()

        with ExecContext():
            self.httpd_queue = multiprocessing.Queue()
            webserver_proc = multiprocessing.Process(target=webserver,
                                                     args=(self.httpd_queue,))
            webserver_proc.start()
            self.httpd_port = self.httpd_queue.get()

    def tearDown(self):
        "Stops web server"
        self.httpd_queue.put("stop")

    def test_maildir(self):
        "Sends mail to maildir"
        with tempfile.TemporaryDirectory() as maildirname:
            for d in ["cur", "new", "tmp"]:
                _os.makedirs(_os.path.join(maildirname, d))
                _os.makedirs(_os.path.join(maildirname, "inbox", d))
            maildir_cfg = """[DEFAULT]
            to = example@example.com
            email-protocol = maildir
            maildir-path = {}
            maildir-mailbox = inbox
            """.format(maildirname)

            with ExecContext(maildir_cfg) as ctx:
                self.httpd_queue.put("next")
                ctx.call("add", 'test', 'http://127.0.0.1:{port}/gmane/feed.rss'.format(port = self.httpd_port))
                ctx.call("run")

            # quick check to make sure right number of messages sent
            # and subjects are right
            inbox = mailbox.Maildir(_os.path.join(maildirname, "inbox"))
            msgs = list(inbox)

            self.assertEqual(len(msgs), 5)
            self.assertEqual(len([msg for msg in msgs if msg["subject"] == "split massive package into modules"]), 1)
            self.assertEqual(len([msg for msg in msgs if msg["subject"] == "Re: new maintainer and mailing list for rss2email"]), 4)

if __name__ == '__main__':
    unittest.main()
