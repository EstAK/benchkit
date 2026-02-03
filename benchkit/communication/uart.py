# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from . import CommunicationLayer

import serial
import pathlib

from typing import Iterable

from benchkit.utils.types import Command, PathType, Environment


class StatusAware:
    """
    Abstract class for communication layers that are aware of their connection status.
    NOTE: use a python interface ?
    """

    """
    Returns whether the communication layer is open.
    """

    def is_open(self) -> bool: ...

    """
    Starts the communication layer.
    """

    def start_comm(self) -> None: ...

    """
    Performs checks then, closes the communication layer.
    """

    def close_comm(self) -> None: ...

    """
    Closes the communication layer without checking whether it is open.
    """

    def _unchecked_close_comm(self) -> None: ...


class UARTCommLayer(CommunicationLayer, StatusAware):
    """Communication layer to handle a device through UART."""

    def __init__(
        self,
        port: pathlib.Path,
        baudrate: int = 115200,
        timeout: float = 1.0,
        ps1: str | None = None,
    ):
        super().__init__()

        self._port: pathlib.Path = port
        self._baudrate: int = baudrate
        self._timeout: float = timeout
        self._ps1: str | None = ps1
        self._con: serial.Serial | None = None

    def is_open(self) -> bool:
        return self._con is not None

    def start_comm(self) -> None:
        if self.is_open():
            raise RuntimeError("Communication layer is already open.")

        self._con = serial.Serial(
            port=str(self._port),
            baudrate=self._baudrate,
            timeout=self._timeout,
        )

    def close_comm(self) -> None:
        if not self.is_open():
            raise RuntimeError("Communication layer is not open.")
        self._unchecked_close_comm()

    def _unchecked_close_comm(self) -> None:
        self._con.close()  # type: ignore

    def shell(
        self,
        command: Command,
        std_input: str | None = None,
        current_dir: PathType | None = None,
        environment: Environment = None,
        shell: bool = False,
        print_input: bool = True,
        print_output: bool = True,
        print_curdir: bool = True,
        timeout: int | None = None,
        output_is_log: bool = False,
        ignore_ret_codes: Iterable[int] = (),
        ignore_any_error_code: bool = False,
    ) -> str:
        """Run a shell command on the target host.

        Args:
            command (Command):
                command to run on the target host.
            std_input (str | None, optional):
                input to pipe into the command to run, None if there is no input to provide.
                Defaults to None.
            current_dir (PathType | None, optional):
                directory where to run the command. Defaults to None.
            environment (Environment, optional):
                environment to pass to the command to run. Defaults to None.
            shell (bool, optional):
                whether a shell must be created to run the command. Defaults to False.
            print_input (bool, optional):
                whether to print the command on benchkit logs. Defaults to True.
            print_output (bool, optional):
                whether to print the command output on benchkit logs. Defaults to True.
            print_curdir (bool, optional):
                whether to print the current directoru on benchkit logs. Defaults to True.
            timeout (int | None, optional):
                number of seconds to wait for the command to complete, or None for no timeout.
                Defaults to None.
            output_is_log (bool, optional):
                whether the output of the command is expected to be logging (e.g., when running
                `cmake`). If it is the case, the logging will be printed in a `tail -f` fashion.
                Defaults to False.
            ignore_ret_codes (Iterable[int], optional):
                List of error code to ignore if it is the return code of the command.
                Defaults to () (empty collection).
            ignore_any_error_code (bool, optional):
                whether to error any error code returned by the command.

        Returns:
            str: the output of the command.
        """
        if not self.is_open():
            raise RuntimeError("Communication layer is not open.")

        cmd: str = " ".join(command) if isinstance(command, list) else command

        if print_input:
            print(f"[input]{cmd}")

        writtren_bytes: int = self._con.write(cmd.encode() + b"\n")  # type: ignore

        if writtren_bytes != len(cmd) + 1:
            raise RuntimeError("Failed to write the full command to UART.")

        ret: str = self._con.readall().decode()  # type: ignore
        if self._ps1 is not None:
            ret = ret.replace(self._ps1, "")
        ret = ret.replace(cmd, "").strip()

        if print_output:
            print(ret)

        return ret

    def __enter__(self) -> "UARTCommLayer":
        self.start_comm()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close_comm()
