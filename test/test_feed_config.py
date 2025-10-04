#!/usr/bin/env python3

"""Test feed configuration logic."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, Path(__file__).absolute().parent.joinpath("util").as_posix())
from util.execcontext import ExecContext


class TestFeedConfig(unittest.TestCase):
    def test_user_agent_substitutions(self):
        """User agent with substitutions done is not written to config"""
        # Previously, if e.g. "r2e __VERSION__" was in the top level
        # user-agent config var, the substituted version (e.g. "r2e 3.11")
        # was written to the per-feed configs due to the fact the
        # substitution happened when we loaded the config. We want the
        # un-substituted versions written.
        sub_cfg = """
[DEFAULT]
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
        """Badly substituted user agent from v3.11 is corrected"""
        # If someone added feeds with version 3.11, they would've had badly
        # substituted user agent strings written to their configs. We want to
        # fix them and write in unsubstituted values. Note: we only fix the
        # config if the user had the default 3.11 user agent, we can't know
        # what they really meant if they have a non-default one.
        bad_sub_cfg = """
[DEFAULT]
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
        """Verbose setting set to debug in configuration should be respected"""
        cfg = """
[DEFAULT]
verbose = debug
"""
        with ExecContext(cfg) as ctx:
            p = ctx.call("run", "--no-send")
        self.assertIn("[DEBUG]", p.stderr)

    def test_verbose_setting_info(self):
        """Verbose setting set to info in configuration should be respected"""
        cfg = """
[DEFAULT]
verbose = info
"""
        with ExecContext(cfg) as ctx:
            p = ctx.call("run", "--no-send")
        self.assertNotIn("[DEBUG]", p.stderr)


if __name__ == "__main__":
    unittest.main()
