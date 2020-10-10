import collections
import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Any

# We run the r2e in the dir above this script, not the system-wide
# installed version, which you probably don't mean to test.
r2e_path = str(Path(__file__).absolute().parent.parent.parent.joinpath("r2e"))
sys.path.insert(0, os.path.dirname(r2e_path))

import rss2email
import rss2email.main

# Mimic the subprocess.CompletedProcess api.
ProcessStub = collections.namedtuple(
    'ProcessStub', ['stdout', 'stderr', 'returncode'])


class TeeIO(io.TextIOWrapper):
    def __init__(self, *args, tee=None):
        self.tee = tee
        super().__init__(*args)

    def write(self, s):
        self.tee.write(s)
        return super().write(s)


@contextlib.contextmanager
def capture_output(suppress=True):
    # Adapted from: https://stackoverflow.com/a/64289688/1938621.
    output = {}
    try:
        # Redirect
        if suppress:
            sys.stdout = io.TextIOWrapper(io.BytesIO(), sys.stdout.encoding)
            sys.stderr = io.TextIOWrapper(io.BytesIO(), sys.stderr.encoding)
        else:
            sys.stdout = TeeIO(
                io.BytesIO(), sys.stdout.encoding, tee=sys.stdout)
            sys.stderr = TeeIO(
                io.BytesIO(), sys.stderr.encoding, tee=sys.stderr)
        assert len(rss2email.LOG.handlers) == 1
        rss2email.LOG.handlers[0].stream = sys.stderr
        yield output
    finally:
        # Read
        sys.stdout.seek(0)
        sys.stderr.seek(0)
        output['stdout'] = sys.stdout.read()
        output['stderr'] = sys.stderr.read()
        sys.stdout.close()
        sys.stderr.close()

        # Restore
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        rss2email.LOG.handlers[0].stream = sys.stderr


class ExecContext:
    """Creates temporary config, data file and lets you call r2e with them
    easily. Cleans up temp files afterwards.

    Example:

    with ExecContext(config="[DEFAULT]\nto=me@example.com") as context:
        context.call("run", "--no-send")

    """

    def __init__(self, config: str):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self._tmpdir.name, "rss2email.cfg")
        self.data_path = Path(self._tmpdir.name, "rss2email.json")
        self.opml_path = Path(self._tmpdir.name, "rss2email.opml")

        self.cfg_path.write_text(config)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._tmpdir.cleanup()

    def call(self, *args):
        return subprocess.run(
            [sys.executable, r2e_path, "-c", str(self.cfg_path), "-d", str(self.data_path)] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True)

    def change_config(self, params: Dict[str, Any]) -> None:
        config = ConfigParser()
        config.read(str(self.cfg_path))
        for name, value in params.items():
            config['DEFAULT'][name] = str(value)
        with self.cfg_path.open('w') as file:
            config.write(file)


class RunContext(ExecContext):
    """ Run rss2email calls within the same python process. """
    suppress = True

    def call(self, *args):
        importlib.reload(rss2email.config)
        rss2email.LOG.setLevel(
            rss2email.config.CONFIG['DEFAULT']['verbose'].upper())

        with capture_output(suppress=self.suppress) as output:
            rss2email.main.run(
                ["-c", str(self.cfg_path), "-d", str(self.data_path)] +
                list(args))

        return ProcessStub(
            stdout=output['stdout'],
            stderr=output['stderr'],
            returncode=0)
