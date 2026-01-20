#!/usr/bin/env python3

import pathlib

from dataclasses import dataclass
from benchkit.platforms import Platform
from benchkit.shell.shellasync import shell_async, AsyncProcess


@dataclass
class SchedulerExtension:
    platform: Platform
    path_to_extension: pathlib.Path
    out_dir: pathlib.Path
    _process: AsyncProcess | None = None

    """
    Base class for scheduler extensions.
    """

    def __enter__(self) -> AsyncProcess:
        self._process = shell_async(
            command=str(self.path_to_extension),
            stdout_path=self.out_dir / "out.txt",
            stderr_path=self.out_dir / "err.txt",
            platform=self.platform,
        )
        return self._process

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        if self._process is None:
            raise RuntimeError("SchedulerExtension process was not started.")

        self._process.stop()
