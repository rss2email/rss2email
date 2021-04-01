import os
import tempfile
from pathlib import Path


class TemporarySendmail:
    def __init__(self, exitcode):
        self._tmpdir = tempfile.TemporaryDirectory()

        _config = tempfile.NamedTemporaryFile(
            dir=self._tmpdir.name, delete=False)
        self.config = Path(_config.name)

        with tempfile.NamedTemporaryFile(
                dir=self._tmpdir.name, delete=False) as _bin:
            _bin.write(
                b'''#!/bin/sh
                echo "Sendmail failing for reasons..."
                exit %s''' % bytes(str(exitcode), 'utf-8'))
        self.bin = Path(_bin.name)
        os.chmod(str(self.bin), 0o700)

    def cleanup(self):
        self._tmpdir.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
