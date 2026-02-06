#!/usr/bin/env python3

import time

from benchkit.commandwrappers.stressng import StressNgContext
from benchkit.platforms import get_current_platform
from benchkit.platforms.generic import GenericPlatform
from benchkit.communication.uart import UARTCommLayer

if __name__ == "__main__":
    platform = (
        GenericPlatform(
            comm_layer=UARTCommLayer(
                port="/dev/ttyUSB0",
                baudrate=115200,
                timeout=1.0,
            )
        )
        if True  # toggle between UART and generic platform for testing
        else get_current_platform()
    )

    before: float = time.monotonic()
    with StressNgContext(
        args={"--cpu": "2"},
        cmds=[],
        platform=platform,
    ):
        time.sleep(10)
    duration: float = time.monotonic() - before
    target_duration: float = (
        14.0 if True else 10.0
    )  # adjust target duration for UART platform
    assert round(duration, 0) == target_duration, (
        f"Expected duration to be around {target_duration} seconds, but got {duration:.2f} seconds"
    )
