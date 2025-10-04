#!/usr/bin/env python3

"""Test retrieving feeds from servers."""

import multiprocessing
import unittest
import urllib.request

if multiprocessing.get_start_method(allow_none=True) is None:
    multiprocessing.set_start_method("spawn", force=True)

from test.util.tempsendmail import TemporarySendmail
from test.util.execcontext import ExecContext, r2e_path
from rss2email import feed
from rss2email import util
import http.server
import io
import subprocess
import time
import sys
import json
import os as _os
from pathlib import Path


from rss2email.feeds import UNIX

# Directory containing test feed data/configs
test_dir = str(Path(__file__).absolute().parent.joinpath("data"))


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
    httpd = http.server.HTTPServer(("", 0), NoLogHandler)
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


def webserver_for_test_user_agent(queue):
    class AgentDumper(NoLogHandler):
        def do_GET(self):
            queue.put(self.headers["User-Agent"])
            super().do_GET()

    httpd = http.server.HTTPServer(("", 0), AgentDumper)
    try:
        port = httpd.server_address[1]
        queue.put(port)
        httpd.handle_request()
    finally:
        httpd.server_close()


def webserver_for_test_if_fetch(queue, timeout):
    """Spawn a webserver for `timeout` seconds"""
    httpd = http.server.HTTPServer(("", 0), NoLogHandler)
    httpd.timeout = timeout
    try:
        port = httpd.server_address[1]
        queue.put(port)

        httpd.handle_request()
        queue.put("done")
    finally:
        httpd.server_close()


import urllib.request

from test.util.tempsendmail import TemporarySendmail
from rss2email import feed
from rss2email import util


class TestFetch(unittest.TestCase):
    "Retrieving feeds from servers"

    def test_delay(self):
        "Waits before fetching repeatedly from the same server"
        wait_time = 0.3
        delay_cfg = """[DEFAULT]
        to = example@example.com
        same-server-fetch-interval = {}
        """.format(
            wait_time
        )

        num_requests = 3

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(
            target=webserver_for_test_fetch, args=(queue, num_requests, wait_time)
        )
        webserver_proc.start()
        port = queue.get()

        with ExecContext(delay_cfg) as ctx:
            for i in range(num_requests):
                ctx.call(
                    "add",
                    "test{i}".format(i=i),
                    "http://127.0.0.1:{port}/disqus/feed.rss".format(port=port),
                )
            ctx.call("run", "--no-send")

        result = queue.get()

        if result == "too fast":
            raise Exception("r2e did not delay long enough!")

    def test_http_user_agent_config(self):
        http_user_agent = "my-test-agent"
        http_user_agent_cfg = """[DEFAULT]
        to = example@example.com
        user-agent = {}
        """.format(
            http_user_agent
        )

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(
            target=webserver_for_test_user_agent, args=(queue,)
        )
        webserver_proc.start()
        port = queue.get()

        with ExecContext(http_user_agent_cfg) as ctx:
            ctx.call("add", "test", "http://127.0.0.1:{port}/dummy".format(port=port))
            ctx.call("run", "--no-send")
        self.assertEqual(queue.get(), http_user_agent)

    def test_default_http_user_agent(self):
        http_default_agent_cfg = """[DEFAULT]
        to = example@example.com
        """

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(
            target=webserver_for_test_user_agent, args=(queue,)
        )
        webserver_proc.start()
        port = queue.get()

        with ExecContext(http_default_agent_cfg) as ctx:
            ctx.call("add", "test", "http://127.0.0.1:{port}/dummy".format(port=port))
            ctx.call("run", "--no-send")
        self.assertIn(
            "rss2email/",
            queue.get(),
            "rss2email should identify itself as the User-Agent by default",
        )

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
            command = [
                sys.executable,
                r2e_path,
                "-VVVVV",
                "-c",
                str(ctx.cfg_path),
                "-d",
                str(ctx.data_path),
                "run",
                "--no-send",
            ]
            processes = [
                subprocess.Popen(
                    command, stdout=output_fd, stderr=output_fd, close_fds=True
                )
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
            with io.open(input_fd, "r", buffering=1) as file:
                for line in file:
                    if "acquired lock" in line and previous_line is not None:
                        finish_precedes_acquire = (
                            finish_precedes_acquire
                            and "save feed data" in previous_line
                        )
                    previous_line = line
            self.assertTrue(finish_precedes_acquire)

    def test_only_new(self):
        "Add and fetch contents"

        standard_cfg = """[DEFAULT]
        to = example@example.com"""

        queue = multiprocessing.Queue()
        webserver_proc = multiprocessing.Process(
            target=webserver_for_test_if_fetch, args=(queue, 10)
        )
        webserver_proc.start()
        port = queue.get()

        with ExecContext(standard_cfg) as ctx:
            ctx.call(
                "add",
                "--only-new",
                "test",
                "http://127.0.0.1:{port}/disqus/feed.rss".format(port=port),
            )
            # check if data is written
            self.assertTrue(_os.path.exists(ctx.data_path))
            with ctx.data_path.open("r") as f:
                content = json.load(f)
                # check if entries in seen
                self.assertIn("seen", content["feeds"][0])
        self.assertEqual(queue.get(), "done")


if __name__ == "__main__":
    unittest.main()
