#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import signal

from benchkit.platforms import Platform
from benchkit.shell.shellasync import shell_async, AsyncProcess

from typing import Any


class StressNgContext:
    def __init__(
        self,
        args: dict[str, Any],
        cmds: list[str],
        platform: Platform,
    ) -> None:
        self._cmd: list[str] = ["stress-ng"] + cmds
        self._args: dict[str, Any] = args
        self._platform: Platform = platform
        self._async_process: AsyncProcess | None = None

    def add_args(self, args: dict[str, Any]) -> None:
        self._args.update(args)

    def add_cmd(self, cmd: str) -> None:
        self._cmd.append(cmd)

    def start(self) -> None:
        cmd: list[str] = self._cmd
        for k, v in self._args.items():
            cmd.extend([k, str(v)])

        self._async_process = shell_async(
            command=cmd,
            stdout_path="/dev/null",  # HACK how to get devnull on non linux
            stderr_path="/dev/null",
            platform=self._platform,
            ignore_ret_codes=False,
        )

    def end(self) -> None:
        if self._async_process is not None:
            self._platform.comm.signal(
                pid=self._async_process.pid,
                signal_code=signal.SIGINT,
            )
        else:
            raise Exception("End should not be called without previously calling end")

    def __enter__(self):
        self.start()

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            print(f"Exception: {exception_type.__name__}: {exception_value}")
        self.end()
