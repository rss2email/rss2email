import os
import subprocess
import sys
import tempfile
from pathlib import Path


# By default, we run the r2e in the dir above this script, not the
# system-wide installed version, which you probably don't mean to
# test. You can also pass in an alternate location in the R2E_PATH
# environment variable.
r2e_path = os.getenv("R2E_PATH", Path(__file__).absolute().parent.parent.parent.joinpath("r2e"))


class ExecContext:
    """Creates temporary config, data file and lets you call r2e with them
    easily. Cleans up temp files afterwards.

    Example:

    with ExecContext(config="[DEFAULT]\nto=me@example.com") as context:
        context.call("run", "--no-send")

    """
    def __init__(self, config):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, "rss2email.cfg")
        self.data_path = os.path.join(self.tmpdir, "rss2email.json")
        self.opml_path = os.path.join(self.tmpdir, "rss2email.opml")

        with open(self.cfg_path, "w") as f:
            f.write(config)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        for path in [self.cfg_path, self.data_path, self.opml_path]:
            if os.path.exists(path):
                os.remove(path)
        os.rmdir(self.tmpdir)

    def call(self, *args):
        subprocess.call([sys.executable, r2e_path, "-c", self.cfg_path, "-d", self.data_path] + list(args))
