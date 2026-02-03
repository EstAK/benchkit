#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from benchkit.communication.uart import UARTCommLayer

if __name__ == "__main__":
    with UARTCommLayer(
        port=pathlib.Path("/dev/ttyUSB0"),
        baudrate=115200,
        timeout=1.0,
        ps1="~ #",
    ) as uart:
        uart.shell(command="ls", print_output=True, print_input=False,)
