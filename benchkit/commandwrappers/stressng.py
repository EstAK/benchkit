#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import re
import signal

from benchkit.platforms import Platform
from benchkit.shell.shellasync import shell_async, AsyncProcess
from benchkit.communication.uart import UARTCommLayer

from typing import Any, Self


class StressNgContext:
    def __new__(cls, args, cmds, platform):
        cls = (
            UARTStressNgContext
            if isinstance(platform.comm, UARTCommLayer)
            else GenericStressNgContext
        )
        return super().__new__(cls)

    def __init__(
        self,
        args: dict[str, Any],
        cmds: list[str],
        platform: Platform,
    ) -> None:
        self._cmd: list[str] = ["stress-ng"] + cmds
        self._args: dict[str, Any] = args
        self._platform: Platform = platform

        # FIXME add check for stress-ng, code below is commented out for now
        # if "FALSE" in self._platform.comm.shell(
        #     command="which stress-ng >/dev/null 2>&1 || echo FALSE",
        #     print_curdir=False,
        #     print_input=False,
        #     print_output=False,
        #     shell=True,
        # ):
        #     raise Exception("stress-ng is not installed on the target platform")

    @property
    def cmd(self) -> list[str]:
        cmd: list[str] = self._cmd
        for k, v in self._args.items():
            cmd.extend([k, str(v)])

        return cmd

    def downcast(self) -> "StressNgContext":
        return (
            UARTStressNgContext(self._args, self._cmd, self._platform)
            if isinstance(self._platform.comm, UARTCommLayer)
            else GenericStressNgContext(self._args, self._cmd, self._platform)
        )

    def add_args(self, args: dict[str, Any]) -> None:
        self._args.update(args)

    def add_cmd(self, cmd: str) -> None:
        self._cmd.append(cmd)

    def __enter__(self):
        self.start()

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_type is not None:
            print(f"Exception: {exception_type.__name__}: {exception_value}")
        self.end()

    def start(self) -> None:
        raise NotImplementedError("Start method should be implemented by subclass")

    def end(self) -> None:
        raise NotImplementedError("End method should be implemented by subclass")


class GenericStressNgContext(StressNgContext):
    def __init__(
        self,
        args: dict[str, Any],
        cmds: list[str],
        platform: Platform,
    ) -> None:
        self._async_process: AsyncProcess | None = None
        self._cmd: list[str] = ["stress-ng"] + cmds
        self._args: dict[str, Any] = args
        self._platform: Platform = platform

    def start(self) -> None:
        self._async_process = shell_async(
            command=self.cmd,
            stdout_path="/dev/null",  # HACK only works on *nix
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


class UARTStressNgContext(StressNgContext):
    def __init__(
        self,
        args: dict[str, Any],
        cmds: list[str],
        platform: Platform,
    ) -> None:
        if not isinstance(platform.comm, UARTCommLayer):
            raise Exception("UARTStressNgContext requires a UART communication layer")

        self._cmd: list[str] = ["stress-ng"] + cmds
        self._args: dict[str, Any] = args
        self._platform: Platform = platform
        self._pid: int | None = None

    def start(self) -> None:
        cmd_str: str = " ".join(self.cmd) + " &"
        ret: str = self._platform.comm.shell(command=cmd_str, print_output=False, shell=True)
        ret = " ".join(ret.splitlines()[1::])

        if (match := re.search(r"\[([^\]]+)\]", ret)):
            self._pid = int(match.group(1))


    def end(self) -> None:
        self._platform.comm.signal(pid=self._pid, signal_code=signal.SIGINT)

