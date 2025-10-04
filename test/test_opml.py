#!/usr/bin/env python3

"""Test OPML import/export functionality."""

import unittest
import json
import sys
from pathlib import Path

sys.path.insert(0, Path(__file__).absolute().parent.joinpath("util").as_posix())
from util.execcontext import ExecContext


class TestOPML(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestOPML, self).__init__(*args, **kwargs)

        self.cfg = "[DEFAULT]\nto = example@example.com"
        self.feed_name = "test"
        self.feed_url = "https://example.com/feed.xml"
        self.opml_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<opml version=\"1.0\">
<head>
<title>rss2email OPML export</title>
</head>
<body>
<outline type=\"rss\" text=\"{}\" xmlUrl=\"{}"/>
</body>
</opml>
""".format(
            self.feed_name, self.feed_url
        ).encode()

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

            with ctx.data_path.open("r") as f:
                content = json.load(f)

            self.assertEqual(content["feeds"][0]["name"], self.feed_name)


if __name__ == "__main__":
    unittest.main()
