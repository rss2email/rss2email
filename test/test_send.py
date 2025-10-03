#!/usr/bin/env python3

"""Test sending email using the various email-protocol choices."""

import multiprocessing
import unittest
import http.server
import sys
import mailbox
from pathlib import Path
from typing import List

sys.path.insert(0, Path(__file__).absolute().parent.joinpath("util").as_posix())
from util.execcontext import ExecContext
from util.tempmaildir import TemporaryMaildir
from util.tempsendmail import TemporarySendmail

# Directory containing test feed data/configs
test_dir = str(Path(__file__).absolute().parent.joinpath("data"))


class NoLogHandler(http.server.SimpleHTTPRequestHandler):
    """No logging handler serving test feed data from test_dir"""

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


def webserver_for_test_send(queue):
    httpd = http.server.HTTPServer(("", 0), NoLogHandler)
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
    """Send email using the various email-protocol choices"""

    def setUp(self):
        """Starts web server to serve feeds"""
        self.httpd_queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(
            target=webserver_for_test_send, args=(self.httpd_queue,)
        )
        webserver_proc.start()
        self.httpd_port = self.httpd_queue.get()

    def tearDown(self):
        """Stops web server"""
        self.httpd_queue.put("stop")

    def test_maildir(self):
        """Sends mail to maildir"""
        with TemporaryMaildir() as maildir:
            maildir_cfg = """
                [DEFAULT]
                to = example@example.com
                email-protocol = maildir
                maildir-path = {maildir_path}
                maildir-mailbox = {maildir_mailbox}
                """.format(
                maildir_path=maildir.path, maildir_mailbox=maildir.inbox_name
            )

            with ExecContext(maildir_cfg) as ctx:
                self.httpd_queue.put("next")
                ctx.call(
                    "add",
                    "test",
                    "http://127.0.0.1:{port}/gmane/feed.rss".format(
                        port=self.httpd_port
                    ),
                )
                ctx.call("run")

            # quick check to make sure right number of messages sent
            # and subjects are right
            msgs = maildir.inbox.values()  # type: List[mailbox.MaildirMessage]

            self.assertEqual(len(msgs), 5)
            self.assertEqual(
                len(
                    [
                        msg
                        for msg in msgs
                        if msg["subject"] == "split massive package into modules"
                    ]
                ),
                1,
            )
            self.assertEqual(
                len(
                    [
                        msg
                        for msg in msgs
                        if msg["subject"]
                        == "Re: new maintainer and mailing list for rss2email"
                    ]
                ),
                4,
            )

    def _test_sendmail(self, exitcode, shouldlog, verbose="error"):
        with TemporarySendmail(exitcode) as sendmail:
            cfg = """
            [DEFAULT]
            to = example@example.com
            sendmail = {sendmail}
            sendmail_config = {sendmail_config}
            verbose = {verbose}
            """.format(
                sendmail=sendmail.bin, sendmail_config=sendmail.config, verbose=verbose
            )

            with ExecContext(cfg) as ctx:
                self.httpd_queue.put("next")
                ctx.call(
                    "add",
                    "test",
                    "http://127.0.0.1:{port}/gmane/feed.rss".format(
                        port=self.httpd_port
                    ),
                )
                p = ctx.call("run")

        assertion = self.assertIn if shouldlog else self.assertNotIn
        assertion("Sendmail failing for reasons...", p.stderr)

    def test_sendmail_success(self):
        self._test_sendmail(exitcode=0, shouldlog=False)

    def test_sendmail_fail(self):
        self._test_sendmail(exitcode=1, shouldlog=True)

    def test_sendmail_debug(self):
        self._test_sendmail(exitcode=0, shouldlog=True, verbose="debug")


if __name__ == "__main__":
    unittest.main()
