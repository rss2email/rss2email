#!/usr/bin/env python3

"""Test processing logic on known feeds.
"""

import difflib as _difflib
import glob as _glob
import io as _io
import os as _os
import platform
import re as _re
import multiprocessing
import subprocess
import unittest
import mailbox
import http.server
import time
import sys
import json
from pathlib import Path
from typing import List

sys.path.insert(0, _os.path.dirname(__file__))
from util.execcontext import r2e_path, ExecContext
from util.tempmaildir import TemporaryMaildir
from util.tempsendmail import TemporarySendmail

# Directory containing test feed data/configs
test_dir = str(Path(__file__).absolute().parent.joinpath("data"))

# Ensure we import the local (not system-wide) rss2email module
sys.path.insert(0, _os.path.dirname(r2e_path))
import rss2email as _rss2email
import rss2email.config as _rss2email_config
import rss2email.feed as _rss2email_feed
from rss2email.feeds import UNIX

# This metaclass lets us generate the tests for each feed directory
# separately. This lets us see which tests are being run more clearly than
# if we had one big test that ran everything.
class TestEmailsMeta(type):
    def __new__(cls, name, bases, attrs):
        # no paths on the command line, find all subdirectories
        this_dir = _os.path.dirname(__file__)

        # we need standardized URLs, so change to `this_dir` and adjust paths
        _os.chdir(this_dir)

        # Generate test methods
        for test_config_path in _glob.glob("data/*/*.config"):
            test_name = "test_email_{}".format(test_config_path)
            attrs[test_name] = cls.generate_test(test_config_path)

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
            r'^Message-ID: <(.*)@{}>$'.format(_re.escape(platform.node())), _re.MULTILINE)
        self.USER_AGENT_REGEXP = _re.compile(
            r'^User-Agent: rss2email/{0} \({1}\)$'.format(_re.escape(_rss2email.__version__), _re.escape(_rss2email.__url__)),
            _re.MULTILINE)
        self.BOUNDARY_REGEXP = _re.compile('===============[^=]+==')

    def clean_result(self, text):
        """Cleanup dynamic portions of the generated email headers

        >>> text = (
        ...      'Content-Type: multipart/digest;\\n'
        ...      '  boundary="===============7509425281347501533=="\\n'
        ...      'MIME-Version: 1.0\\n'
        ...      'Date: Tue, 23 Aug 2011 15:57:37 -0000\\n'
        ...      'Message-ID: <9dff03db-f5a7@mail.example>\\n'
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

    def run_single_test(self, dirname=None, config_path=None):
        if dirname is None:
            dirname = _os.path.dirname(config_path)
        if config_path is None:
            _rss2email.LOG.info('testing {}'.format(dirname))
            for config_path in _glob.glob(_os.path.join(dirname, '*.config')):
                self.run_single_test(dirname=dirname, config_path=config_path)
            return
        feed_path = _glob.glob(_os.path.join(dirname, 'feed.*'))[0]

        _rss2email.LOG.info('testing {}'.format(config_path))
        config = _rss2email_config.Config()
        config.read_string(self.BASE_CONFIG_STRING)
        read_paths = config.read([config_path])
        feed = _rss2email_feed.Feed(name='test', url=Path(feed_path).as_posix(), config=config)
        feed._send = TestEmails.Send()
        feed.run()
        generated = feed._send.as_string()
        generated = self.clean_result(generated)

        expected_path = config_path.replace('config', 'expected')
        if not _os.path.exists(expected_path):
            if _os.environ.get('FORCE_TESTDATA_CREATION', '') == '1':
                with open(expected_path, 'w') as f:
                    f.write(generated)
                raise ValueError('missing expected test data, now created')
            else:
                raise ValueError('missing test; set FORCE_TESTDATA_CREATION=1 to create')
        else:
            with open(expected_path, 'r') as f:
                expected = f.read()
        if generated != expected:
            diff_lines = _difflib.unified_diff(
                expected.splitlines(), generated.splitlines(),
                'expected', 'generated', lineterm='')
            raise ValueError(
                'error processing {}\n{}'.format(
                    config_path,
                    '\n'.join(diff_lines)))

class NoLogHandler(http.server.SimpleHTTPRequestHandler):
    "No logging handler serving test feed data from test_dir"

    if sys.version_info >= (3, 7):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, directory=test_dir)
    else:
        def translate_path(self, path):
            cwd = _os.getcwd()
            try:
                _os.chdir(test_dir)
                return super().translate_path(path)
            finally:
                _os.chdir(cwd)

    def log_message(self, format, *args):
        return

def webserver_for_test_fetch(queue, num_requests, wait_time):
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

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(target=webserver_for_test_fetch, args=(queue, num_requests, wait_time))
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
        if not UNIX:
            self.skipTest("No locking on Windows.")

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
            command = [sys.executable, r2e_path, "-VVVVV",
                       "-c", str(ctx.cfg_path),
                       "-d", str(ctx.data_path),
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
                all_success = all_success and (p.returncode == 0)
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

def webserver_for_test_send(queue):
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

class TestSend(unittest.TestCase):
    "Send email using the various email-protocol choices"
    def setUp(self):
        "Starts web server to serve feeds"
        self.httpd_queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(target=webserver_for_test_send, args=(self.httpd_queue,))
        webserver_proc.start()
        self.httpd_port = self.httpd_queue.get()

    def tearDown(self):
        "Stops web server"
        self.httpd_queue.put("stop")

    def test_maildir(self):
        "Sends mail to maildir"
        with TemporaryMaildir() as maildir:
            maildir_cfg = """\
                [DEFAULT]
                to = example@example.com
                email-protocol = maildir
                maildir-path = {maildir_path}
                maildir-mailbox = {maildir_mailbox}
                """.format(maildir_path=maildir.path,
                           maildir_mailbox=maildir.inbox_name)

            with ExecContext(maildir_cfg) as ctx:
                self.httpd_queue.put("next")
                ctx.call("add", 'test', 'http://127.0.0.1:{port}/gmane/feed.rss'.format(port = self.httpd_port))
                ctx.call("run")

            # quick check to make sure right number of messages sent
            # and subjects are right
            msgs = maildir.inbox.values() # type: List[mailbox.MaildirMessage]

            self.assertEqual(len(msgs), 5)
            self.assertEqual(len([msg for msg in msgs if msg["subject"] == "split massive package into modules"]), 1)
            self.assertEqual(len([msg for msg in msgs if msg["subject"] == "Re: new maintainer and mailing list for rss2email"]), 4)

    def _test_sendmail(self, exitcode, shouldlog, verbose='error'):
        with TemporarySendmail(exitcode) as sendmail:
            cfg = """\
            [DEFAULT]
            to = example@example.com
            sendmail = {sendmail}
            sendmail_config = {sendmail_config}
            verbose = {verbose}
            """.format(
                sendmail=sendmail.bin,
                sendmail_config=sendmail.config,
                verbose=verbose)

            with ExecContext(cfg) as ctx:
                self.httpd_queue.put("next")
                ctx.call(
                    "add",
                    'test',
                    'http://127.0.0.1:{port}/gmane/feed.rss'.format(
                        port=self.httpd_port))
                p = ctx.call("run")

        assertion = self.assertIn if shouldlog else self.assertNotIn
        assertion("Sendmail failing for reasons...", p.stderr)

    def test_sendmail_success(self):
        self._test_sendmail(exitcode=0, shouldlog=False)

    def test_sendmail_fail(self):
        self._test_sendmail(exitcode=1, shouldlog=True)

    def test_sendmail_debug(self):
        self._test_sendmail(exitcode=0, shouldlog=True, verbose='debug')


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
            with ctx.cfg_path.open("r") as f:
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
            with ctx.cfg_path.open("r") as f:
                lines = f.readlines()

            feed_cfg_start = lines.index("[feed.test]\n")

            # The bad user-agent should have been removed from the old feed
            # config and not added to the feed we just added.
            for line in lines[feed_cfg_start:]:
                self.assertFalse("user-agent" in line)

    def test_verbose_setting_debug(self):
        "Verbose setting set to debug in configuration should be respected"
        cfg = """[DEFAULT]
        verbose = debug
        """
        with ExecContext(cfg) as ctx:
            p = ctx.call("run", "--no-send")
        self.assertIn('[DEBUG]', p.stderr)

    def test_verbose_setting_info(self):
        "Verbose setting set to info in configuration should be respected"
        cfg = """[DEFAULT]
        verbose = info
        """
        with ExecContext(cfg) as ctx:
            p = ctx.call("run", "--no-send")
        self.assertNotIn('[DEBUG]', p.stderr)


class TestOPML(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestOPML, self).__init__(*args, **kwargs)

        self.cfg = "[DEFAULT]\nto = example@example.com"
        self.feed_name = "test"
        self.feed_url = "https://example.com/feed.xml"
        self.opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
<head>
<title>rss2email OPML export</title>
</head>
<body>
<outline type="rss" text="{}" xmlUrl="{}"/>
</body>
</opml>
""".format(self.feed_name, self.feed_url).encode()

    def test_opml_export(self):
        with ExecContext(self.cfg) as ctx:
            ctx.call("add", self.feed_name, self.feed_url)
            ctx.call("opmlexport", str(ctx.opml_path))

            self.assertTrue(ctx.opml_path.is_file())
            read_content = ctx.opml_path.read_bytes()
            self.assertEqual(self.opml_content, read_content)

    def test_opml_export_without_arg(self):
        with ExecContext(self.cfg) as ctx:
            # This is just a smoke test for now, it'd be better to check
            # stdout but this is enough to check for non-regression
            res = ctx.call("opmlexport")
            self.assertEqual(res.returncode, 0)

            ctx.call("add", self.feed_name, self.feed_url)

            res = ctx.call("opmlexport")
            self.assertEqual(res.returncode, 0)

    def test_opml_import(self):
        with ExecContext(self.cfg) as ctx:
            ctx.opml_path.write_bytes(self.opml_content)
            ctx.call("opmlimport", str(ctx.opml_path))

            with ctx.data_path.open('r') as f:
                content = json.load(f)

            self.assertEqual(content["feeds"][0]["name"], self.feed_name)

if __name__ == '__main__':
    unittest.main()
