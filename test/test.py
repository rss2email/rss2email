#!/usr/bin/env python3

"""Test processing logic on known feeds.
"""

import difflib as _difflib
import glob as _glob
import io as _io
import logging as _logging
import os as _os
import re as _re

import rss2email as _rss2email
import rss2email.config as _rss2email_config
import rss2email.feed as _rss2email_feed


# Get a copy of the internal rss2email.CONFIG for copying
_stringio = _io.StringIO()
_rss2email_config.CONFIG.write(_stringio)
BASE_CONFIG_STRING = _stringio.getvalue()
del _stringio

MESSAGE_ID_REGEXP = _re.compile(
    '^Message-ID: <[^@]*@dev.null.invalid>$', _re.MULTILINE)
USER_AGENT_REGEXP = _re.compile(
    '^User-Agent: rss2email/[0-9.]* \+\S*$', _re.MULTILINE)
BOUNDARY_REGEXP = _re.compile('===============[^=]+==')


class Send (list):
    def __call__(self, sender, message):
        self.append((sender, message))

    def as_string(self):
        chunks = [
            'SENT BY: {}\n{}\n'.format(sender, message.as_string())
            for sender,message in self]
        return '\n'.join(chunks)


def clean_result(text):
    """Cleanup dynamic portions of the generated email headers

    >>> text = (
    ...      'Content-Type: multipart/digest;\\n'
    ...      '  boundary="===============7509425281347501533=="\\n'
    ...      'MIME-Version: 1.0\\n'
    ...      'Date: Tue, 23 Aug 2011 15:57:37 -0000\\n'
    ...      'Message-ID: <9dff03db-f5a7@dev.null.invalid>\\n'
    ...      'User-Agent: rss2email/3.5 +https://github.com/wking/rss2email\\n'
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
            (MESSAGE_ID_REGEXP, 'Message-ID: <...@dev.null.invalid>'),
            (USER_AGENT_REGEXP, 'User-Agent: rss2email/...'),
            (BOUNDARY_REGEXP, '===============...=='),
            ]:
        text = regexp.sub(replacement, text)
    return text

def test(dirname=None, config_path=None, force=False):
    if dirname is None:
        dirname = _os.path.dirname(config_path)
    if config_path is None:
        _rss2email.LOG.info('testing {}'.format(dirname))
        for config_path in _glob.glob(_os.path.join(dirname, '*.config')):
            test(dirname=dirname, config_path=config_path, force=force)
        return
    feed_path = _glob.glob(_os.path.join(dirname, 'feed.*'))[0]
    _rss2email.LOG.info('testing {}'.format(config_path))
    config = _rss2email_config.Config()
    config.read_string(BASE_CONFIG_STRING)
    read_paths = config.read([config_path])
    feed = _rss2email_feed.Feed(name='test', url=feed_path, config=config)
    expected_path = config_path.replace('config', 'expected')
    with open(expected_path, 'r') as f:
        expected = clean_result(f.read())
    feed._send = Send()
    feed.run()
    generated = feed._send.as_string()
    if force:
        with open(expected_path, 'w') as f:
            f.write(generated)
    generated = clean_result(generated)
    if generated != expected:
        diff_lines = _difflib.unified_diff(
            expected.splitlines(), generated.splitlines(),
            'expected', 'generated', lineterm='')
        raise ValueError(
            'error processing {}\n{}'.format(
                config_path,
                '\n'.join(diff_lines)))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--force', action='store_const', const=True,
        help=(
            "write output files (useful for figuring out what's expected "
            'from a new feed).'))
    parser.add_argument(
        '-V', '--verbose', default=0, action='count',
        help='increment verbosity')
    parser.add_argument(
        'dir', nargs='*',
        help='select subdirs to test (tests all subdirs by default)')

    args = parser.parse_args()

    if args.verbose:
        _rss2email.LOG.setLevel(
            max(_logging.DEBUG, _logging.ERROR - 10 * args.verbose))

    # no paths on the command line, find all subdirectories
    this_dir = _os.path.dirname(__file__)
    if not args.dir:
        for basename in _os.listdir(this_dir):
            path = _os.path.join(this_dir, basename)
            if _os.path.isdir(path):
                args.dir.append(path)

    # we need standardized URLs, so change to `this_dir` and adjust paths
    orig_dir = _os.getcwd()
    _os.chdir(this_dir)

    # run tests
    for orig_path in args.dir:
        this_path = _os.path.relpath(orig_path, start=this_dir)
        if _os.path.isdir(this_path):
            test(dirname=this_path, force=args.force)
        else:
            test(config_path=this_path, force=args.force)
