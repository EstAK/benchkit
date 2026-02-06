#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from benchkit.communication.uart import UARTCommLayer
from benchkit.platforms.generic import GenericPlatform

if __name__ == "__main__":
    uart: UARTCommLayer = UARTCommLayer(
        port=pathlib.Path("/dev/ttyUSB0"),
        baudrate=115200,
        timeout=1.0,
    )

    uart.shell(
        command="which stress-ng >/dev/null 2>&1 || echo FALSE",
        print_output=True,
        print_input=False,
    )
