#!/usr/bin/env python3

"""Test processing logic on known feeds.
"""

import difflib as _difflib
import glob as _glob
import io as _io
import os as _os
import re as _re
import tempfile
import multiprocessing
import subprocess
import unittest
import mailbox
import http.server
import time
import sys

# Directory containing test feed data/configs
test_dir = _os.path.dirname(_os.path.abspath(__file__))

# By default, we run the r2e in the dir above this script, not the
# system-wide installed version, which you probably don't mean to
# test.
r2e_path = _os.path.join(test_dir, "..", "r2e")

# Ensure we import the local (not system-wide) rss2email module
sys.path.insert(0, _os.path.dirname(r2e_path))
import rss2email as _rss2email
import rss2email.config as _rss2email_config
import rss2email.feed as _rss2email_feed

# This metaclass lets us generate the tests for each feed directory
# separately. This lets us see which tests are being run more clearly than
# if we had one big test that ran everything.
class TestEmailsMeta(type):
    def __new__(cls, name, bases, attrs):
        # no paths on the command line, find all subdirectories
        this_dir = _os.path.dirname(__file__)
        test_dirs = []
        for basename in _os.listdir(this_dir):
            path = _os.path.join(this_dir, basename)
            if _os.path.isdir(path):
                test_dirs.append(path)

        # we need standardized URLs, so change to `this_dir` and adjust paths
        _os.chdir(this_dir)

        # Generate test methods
        for orig_path in test_dirs:
            this_path = _os.path.relpath(orig_path, start=this_dir)
            test_name = "test_email_{}".format(this_path.replace(".", "_").replace("-", "_"))
            attrs[test_name] = cls.generate_test(this_path)

        return super(TestEmailsMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def generate_test(cls, test_path):
        def fn(self):
            if _os.path.isdir(test_path):
                self.run_single_test(dirname=test_path)
            else:
                self.run_single_test(config_path=test_path)
        return fn

class TestEmails(unittest.TestCase, metaclass=TestEmailsMeta):
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
            r'^User-Agent: rss2email/[0-9.]* (\S*)$', _re.MULTILINE)
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

    def run_single_test(self, dirname=None, config_path=None, force=False):
        if dirname is None:
            dirname = _os.path.dirname(config_path)
        if config_path is None:
            _rss2email.LOG.info('testing {}'.format(dirname))
            for config_path in _glob.glob(_os.path.join(dirname, '*.config')):
                self.run_single_test(dirname=dirname, config_path=config_path, force=force)
            return
        feed_path = _glob.glob(_os.path.join(dirname, 'feed.*'))[0]

        _rss2email.LOG.info('testing {}'.format(config_path))
        config = _rss2email_config.Config()
        config.read_string(self.BASE_CONFIG_STRING)
        read_paths = config.read([config_path])
        feed = _rss2email_feed.Feed(name='test', url=feed_path, config=config)
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
    def __init__(self, config):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = _os.path.join(self.tmpdir, "rss2email.cfg")
        self.data_path = _os.path.join(self.tmpdir, "rss2email.json")

        with open(self.cfg_path, "w") as f:
            f.write(config)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        for path in [self.cfg_path, self.data_path]:
            if _os.path.exists(path):
                _os.remove(path)
        _os.rmdir(self.tmpdir)

    def call(self, *args):
        subprocess.call([r2e_path, "-c", self.cfg_path, "-d", self.data_path] + list(args))

class NoLogHandler(http.server.SimpleHTTPRequestHandler):
    "No logging handler serving test feed data"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, directory=test_dir)

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

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(target=webserver, args=(queue,))
        webserver_proc.start()
        port = queue.get()

        with ExecContext(delay_cfg) as ctx:
            for i in range(num_requests):
                ctx.call("add", 'test{i}'.format(i = i), 'http://127.0.0.1:{port}/disqus/feed.rss'.format(port = port))
            ctx.call("run", "--no-send")

        result = queue.get()

        if result == "too fast":
            raise Exception("r2e did not delay long enough!")

    def test_fetch_parallel(self):
        "Reads/writes to data file are sequenced correctly for multiple instances"
        num_processes = 5
        process_cfg = """[DEFAULT]
        to = example@example.com
        """

        # All r2e instances will output here
        input_fd, output_fd = _os.pipe()

        with ExecContext(process_cfg) as ctx:
            # We don't need to add any feeds - we are testing that the copy
            # and replace dance on the data file is sequenced correctly. r2e
            # always does the copy/replace, it must be sequenced correctly or
            # some processes will exit with a failure since their temp data
            # file was moved out from under them. Proper locking prevents that.
            command = [r2e_path, "-VVVVV",
                       "-c", ctx.cfg_path,
                       "-d", ctx.data_path,
                       "run", "--no-send"]
            processes = [
                subprocess.Popen(command, stdout=output_fd, stderr=output_fd,
                                 close_fds=True)
                for _ in range(num_processes)
            ]
            _os.close(output_fd)

            # Bad locking will cause the victim process to exit with failure.
            all_success = True
            for p in processes:
                p.wait()
                all_success = all_success and (p.returncode == _os.EX_OK)
            self.assertTrue(all_success)

            # We check that each time the lock was acquired, the previous process
            # had finished writing to the data file. i.e. no process ever reads
            # the data file while another has it open.
            previous_line = None
            finish_precedes_acquire = True
            with _io.open(input_fd, 'r', buffering=1) as file:
                for line in file:
                    if "acquired lock" in line and previous_line is not None:
                        finish_precedes_acquire = finish_precedes_acquire and \
                                                  "save feed data" in previous_line
                    previous_line = line
            self.assertTrue(finish_precedes_acquire)

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

        self.httpd_queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(target=webserver, args=(self.httpd_queue,))
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

class TestFeedConfig(unittest.TestCase):
    def test_user_agent_substitutions(self):
        "User agent with substitutions done is not written to config"
        # Previously, if e.g. "r2e __VERSION__" was in the top level
        # user-agent config var, the substituted version (e.g. "r2e 3.11")
        # was written to the per-feed configs due to the fact the
        # substitution happened when we loaded the config. We want the
        # un-substituted versions written.
        sub_cfg = """[DEFAULT]
        to = example@example.com
        user-agent = rss2email __VERSION__
        """

        with ExecContext(sub_cfg) as ctx:
            ctx.call("add", "test", "https://example.com/feed.xml")
            # The old bug was that in the feed-specific config, we would
            # see "user-agent = rss2email 3.11" when in fact user-agent
            # shouldn't appear at all.
            with open(ctx.cfg_path, "r") as f:
                lines = f.readlines()
            feed_cfg_start = lines.index("[feed.test]\n")
            for line in lines[feed_cfg_start:]:
                self.assertFalse("user-agent" in line)

    def test_user_agent_sub_fixed(self):
        "Badly substituted user agent from v3.11 is corrected"
        # If someone added feeds with version 3.11, they would've had badly
        # substituted user agent strings written to their configs. We want to
        # fix them and write in unsubstituted values. Note: we only fix the
        # config if the user had the default 3.11 user agent, we can't know
        # what they really meant if they have a non-default one.
        bad_sub_cfg = """[DEFAULT]
        to = example@example.com
        [feed.test]
        url = https://example.com/feed.xml
        user-agent = rss2email/3.11 (https://github.com/rss2email/rss2email)
        """

        with ExecContext(bad_sub_cfg) as ctx:
            # Modify the config to trigger a rewrite
            ctx.call("add", "other", "https://example.com/other.xml")
            with open(ctx.cfg_path, "r") as f:
                lines = f.readlines()

            feed_cfg_start = lines.index("[feed.test]\n")

            # The bad user-agent should have been removed from the old feed
            # config and not added to the feed we just added.
            for line in lines[feed_cfg_start:]:
                self.assertFalse("user-agent" in line)

if __name__ == '__main__':
    unittest.main()
