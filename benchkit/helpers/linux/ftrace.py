# Copyright (C) 2025 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT
"""
Pythonic interface to tracefs
"""

import pathlib
from benchkit.communication import CommunicationLayer
from benchkit.helpers.linux import kernel
from benchkit.helpers.version import SemanticVersion
from benchkit.utils.types import PathType


def get_tracefs_mount_point(
    comm_layer: CommunicationLayer,
) -> PathType:
    return (
        "/sys/kernel/tracing"
        if kernel.get_version(comm_layer) > SemanticVersion(major=4, minor=1)
        else "/sys/kernel/debug/tracing"
    )


def is_tracefs_mounted(
    comm_layer: CommunicationLayer,
) -> bool:

    command = ["mount", "|", " grep", "tracing"]
    output = comm_layer.shell(command=command, print_input=False, print_output=False).strip()
    mount_point = str(get_tracefs_mount_point(comm_layer=comm_layer))
    return mount_point in output  # only use


def get_current_tracer(
        comm_layer: CommunicationLayer,
) -> str:
    """
    The [list](https://www.kernel.org/doc/html/v4.17/trace/ftrace.html#the-tracers) of possible current tracers
    """
    mount_point = str(pathlib.Path(get_tracefs_mount_point(comm_layer=comm_layer)) / "current_tracer")
    output = comm_layer.shell(command=["cat", mount_point], print_input=False, print_output=False).strip()
    return output


def set_tracing_on(
        tracing_on: bool,
        comm_layer: CommunicationLayer,
):
    mount_point: PathType = (pathlib.Path(get_tracefs_mount_point(comm_layer=comm_layer)) / "trace_on")
    comm_layer.shell(command=["echo", "1" if tracing_on else "0", ">", ], print_output = False, print_curdir= False)


class Tracing:
    def __init__(self, comm_layer: CommunicationLayer):
        self.comm_layer = comm_layer

    def __enter__(self):
        set_tracing_on(tracing_on=True, comm_layer=self.comm_layer)
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        # TODO ask someone what is the correct procedure here
        if exception_type is not None:
            print(f"Exception: {exception_type.__name__}: {exception_value}")
        set_tracing_on(tracing_on=False, comm_layer=self.comm_layer)
