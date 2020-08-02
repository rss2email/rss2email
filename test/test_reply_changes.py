import mailbox
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Dict, Any

sys.path.insert(0, os.path.dirname(__file__))
from util.execcontext import ExecContext
from util.tempmaildir import TemporaryMaildir


class TestReplyChanges(unittest.TestCase):

    def setUp(self) -> None:
        self.maildir = TemporaryMaildir()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.feed_path = Path(self.tmpdir.name, "feed.xml")


    def tearDown(self) -> None:
        self.maildir.cleanup()
        self.tmpdir.cleanup()


    def test_default(self):
        config = self._config()
        self._call(config)

        messages = self.maildir.inbox_messages()
        self.assertEqual(1, len(messages))
        self.assertIsNone(messages[0]['In-Reply-To'])


    def test_off(self):
        config = self._config({"reply-changes": False})
        self._call(config)

        messages = self.maildir.inbox_messages()
        self.assertEqual(1, len(messages))
        self.assertIsNone(messages[0]['In-Reply-To'])


    def test_on(self):
        config = self._config({"reply-changes": True})
        self._call(config)

        messages = self.maildir.inbox_messages()
        self.assertEqual(2, len(messages))
        self.assertIsNone(messages[0]['In-Reply-To'])
        self.assertEqual(messages[0]['Message-ID'], messages[1]['In-Reply-To'])


    def _call(self, config: str):
        with ExecContext(config) as ctx:
            shutil.copyfile("data/nodejs/feed1.xml", str(self.feed_path))
            ctx.call("run")
            shutil.copyfile("data/nodejs/feed2.xml", str(self.feed_path))
            ctx.call("run")


    def test_switch(self):
        config = self._config({"reply-changes": False})
        with ExecContext(config) as ctx:
            shutil.copyfile("data/nodejs/feed1.xml", str(self.feed_path))
            ctx.call("run")
            ctx.change_config({"reply-changes": True})
            ctx.call("run")
            shutil.copyfile("data/nodejs/feed2.xml", str(self.feed_path))
            ctx.call("run")

        messages = self.maildir.inbox_messages() # type: List[mailbox.MaildirMessage]
        self.assertEqual(2, len(messages))
        self.assertIsNone(messages[0]['In-Reply-To'])
        self.assertEqual(messages[0]['Message-ID'], messages[1]['In-Reply-To'])


    def test_no_send(self):
        config = self._config({"reply-changes": True})
        with ExecContext(config) as ctx:
            shutil.copyfile("data/nodejs/feed1.xml", str(self.feed_path))
            ctx.call("run")
            shutil.copyfile("data/nodejs/feed2.xml", str(self.feed_path))
            ctx.call("run", "--no-send")
            shutil.copyfile("data/nodejs/feed3.xml", str(self.feed_path))
            ctx.call("run")

        messages = self.maildir.inbox_messages() # type: List[mailbox.MaildirMessage]
        self.assertEqual(2, len(messages))
        self.assertIsNone(messages[0]['In-Reply-To'])
        self.assertEqual(messages[0]['Message-ID'], messages[1]['In-Reply-To'])


    def _config(self, options: Optional[Dict[str, Any]] = None):
        config = dedent("""\
            [DEFAULT]
            to = mbox@mail.example
            email-protocol = maildir
            maildir-path = {maildir_path}
            maildir-mailbox = {maildir_mailbox}
            """).format(maildir_path=self.maildir.path,
                        maildir_mailbox=self.maildir.inbox_name,
                        url=self.feed_path.absolute())

        if options is not None:
            config += "".join("{0} = {1}\n".format(name, value) for name, value in options.items())

        config += dedent("""\
            [feed.test-feed]
            url = file:{url}
            """).format(url=self.feed_path.absolute())

        return config
