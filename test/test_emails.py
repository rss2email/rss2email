#!/usr/bin/env python3

"""Test processing logic on known feeds."""

import difflib as _difflib
import glob as _glob
import io
import os
import platform
import re as _re
import unittest
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from util.execcontext import r2e_path

# Ensure we import the local (not system-wide) rss2email module
sys.path.insert(0, os.path.dirname(r2e_path))
import rss2email as _rss2email
import rss2email.config as _rss2email_config
import rss2email.feed as _rss2email_feed

# Directory containing test feed data/configs
test_dir = str(Path(__file__).absolute().parent.joinpath("data"))

# This metaclass lets us generate the tests for each feed directory
# separately. This lets us see which tests are being run more clearly than
# if we had one big test that ran everything.
MESSAGE_ID_REGEXP = _re.compile(
    r"^Message-ID: <(.*)@{}>$".format(_re.escape(platform.node())), _re.MULTILINE
)
USER_AGENT_REGEXP = _re.compile(
    r"^User-Agent: rss2email/{0} \({1}\)$".format(
        _re.escape(_rss2email.__version__), _re.escape(_rss2email.__url__)
    ),
    _re.MULTILINE,
)
BOUNDARY_REGEXP = _re.compile("===============[^=]+==")


def clean_result(text, regexes=None):
    """Cleanup dynamic portions of the generated email headers

    >>> text = (
    ...      'Content-Type: multipart/digest;\n'
    ...      '  boundary="===============7509425281347501533=="
    ...      'MIME-Version: 1.0\n'
    ...      'Date: Tue, 23 Aug 2011 15:57:37 -0000\n'
    ...      'Message-ID: <9dff03db-f5a7@mail.example>\n'
    ...      'User-Agent: rss2email/3.5 (https://github.com/rss2email/rss2email)\n'
    ...      )
    >>> regexes = [
    ...     (_re.compile(r'^Message-ID: <.*>$', _re.MULTILINE), 'Message-ID: <...@dev.null.invalid>'),
    ...     (_re.compile(r'^User-Agent: .*$', _re.MULTILINE), 'User-Agent: rss2email/...'),
    ...     (_re.compile('===============[^=]+=='), '===============...=='),
    ... ]
    >>> print(clean_result(text, regexes).rstrip())
    Content-Type: multipart/digest;
      boundary="===============...=="
    MIME-Version: 1.0
    Date: Tue, 23 Aug 2011 15:57:37 -0000
    Message-ID: <...@dev.null.invalid>
    User-Agent: rss2email/...
    """
    if regexes is None:
        regexes = [
            (MESSAGE_ID_REGEXP, "Message-ID: <...@dev.null.invalid>"),
            (USER_AGENT_REGEXP, "User-Agent: rss2email/..."),
            (BOUNDARY_REGEXP, "===============...=="),
        ]
    for regexp, replacement in regexes:
        text = regexp.sub(replacement, text)
    return text


# Generate test methods
for test_config_path in _glob.glob(os.path.join(test_dir, "*", "*.config")):
    test_name = "test_email_{}".format(
        os.path.basename(os.path.dirname(test_config_path))
        + "_"
        + os.path.basename(test_config_path).split(".")[0]
    )

    def make_test_function(config_path, expected_path):
        def test_function():
            original_cwd = os.getcwd()
            test_dir_abs = Path(__file__).absolute().parent
            os.chdir(test_dir_abs)
            try:
                tester = EmailTestBase()
                tester._run_test(config_path, expected_path)
            finally:
                os.chdir(original_cwd)

        return test_function

    globals()[test_name] = make_test_function(
        test_config_path, test_config_path.replace(".config", ".expected")
    )


class EmailTestBase:
    def __init__(self):
        # Get a copy of the internal rss2email.CONFIG for copying
        _stringio = io.StringIO()
        _rss2email_config.CONFIG.write(_stringio)
        self.BASE_CONFIG_STRING = _stringio.getvalue()
        del _stringio

        self.MESSAGE_ID_REGEXP = _re.compile(
            r"^Message-ID: <(.*)@{}>$".format(_re.escape(platform.node())),
            _re.MULTILINE,
        )
        self.USER_AGENT_REGEXP = _re.compile(
            r"^User-Agent: rss2email/{0} \({1}\)$".format(
                _re.escape(_rss2email.__version__), _re.escape(_rss2email.__url__)
            ),
            _re.MULTILINE,
        )
        self.BOUNDARY_REGEXP = _re.compile("===============[^=]+==")

    def clean_result(self, text):
        """Cleanup dynamic portions of the generated email headers"""
        for regexp, replacement in [
            (self.MESSAGE_ID_REGEXP, "Message-ID: <...@dev.null.invalid>"),
            (self.USER_AGENT_REGEXP, "User-Agent: rss2email/..."),
            (self.BOUNDARY_REGEXP, "===============...=="),
        ]:
            text = regexp.sub(replacement, text)
        return text

    def _run_test(self, feed_config_path, expected_email_path):
        class Send(list):
            def __call__(self, sender, message):
                self.append((sender, message))

            def as_string(self):
                chunks = [
                    "SENT BY: {}\n{}\n".format(sender, message.as_string())
                    for sender, message in self
                ]
                return "\n".join(chunks)

        if feed_config_path is None:
            _rss2email.LOG.info("testing {}".format(feed_config_path))
            for config_path in _glob.glob(os.path.join(feed_config_path, "*.config")):
                self._run_test(config_path, config_path.replace(".config", ".expected"))
            return
        feed_path_abs = _glob.glob(
            os.path.join(os.path.dirname(feed_config_path), "feed.*")
        )[0]
        test_dir_abs = Path(__file__).absolute().parent
        feed_path_rel_to_test_dir = (
            Path(feed_path_abs).relative_to(test_dir_abs).as_posix()
        )

        _rss2email.LOG.info("testing {}".format(feed_config_path))
        config = _rss2email_config.Config()
        config.read_string(self.BASE_CONFIG_STRING)
        read_paths = config.read([feed_config_path])
        feed = _rss2email_feed.Feed(
            name="test", url=feed_path_rel_to_test_dir, config=config
        )
        feed._send = Send()
        feed.run()
        generated = feed._send.as_string()
        generated = self.clean_result(generated)

        expected_path = expected_email_path
        if not os.path.exists(expected_path):
            if os.environ.get("FORCE_TESTDATA_CREATION", "") == "1":
                with open(expected_path, "w") as f:
                    f.write(generated)
                raise ValueError("missing expected test data, now created")
            else:
                raise ValueError(
                    "missing test; set FORCE_TESTDATA_CREATION=1 to create"
                )
        else:
            with open(expected_path, "r") as f:
                expected = f.read()
        if generated != expected:
            diff_lines = _difflib.unified_diff(
                expected.splitlines(),
                generated.splitlines(),
                "expected",
                "generated",
                lineterm="",
            )
            raise ValueError(
                "error processing {}\n{}".format(
                    feed_config_path, "\n".join(diff_lines)
                )
            )


if __name__ == "__main__":
    unittest.main()
