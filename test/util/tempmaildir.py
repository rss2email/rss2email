import mailbox
import tempfile
from pathlib import Path


class TemporaryMaildir:
    def __init__(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name)
        mailbox.Maildir(self.path, create=True).close()
        self.inbox_name = "inbox"
        self.inbox = mailbox.Maildir(self.path.joinpath(self.inbox_name), create=True)

    def cleanup(self):
        self.inbox.close()
        self._tmpdir.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
