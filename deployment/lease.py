"""One serving process per private data root; kernel releases locks on exit."""
import fcntl
import os
from pathlib import Path

from .access import AccessError


class ServingLease:
    def __init__(self, root):
        self.path = Path(root) / ".serving.lock"
        self.file = None

    def __enter__(self):
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        self.file = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close(); self.file = None
            raise AccessError(409, "DATA_ROOT_IN_USE", "同一数据根已有服务运行，请停止旧服务后再启动") from None
        return self

    def __exit__(self, *args):
        if self.file is not None:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close(); self.file = None
