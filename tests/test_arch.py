#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import os

from benchkit.helpers.arch import Arch
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    # Test arch_from_str method
    test_values = [
        "arm",
        "ARM64",
        "aarch64",
        "mips",
        "riscv",
        "riscv64",
        "x86",
        "x86_64",
        "amd64",
        "i386",
        "arc",
        "microblaze",
        "xtensa",
        "unknown",  # This should raise an error
    ]

    for value in test_values:
        try:
            arch = Arch.from_str(value)
        except ValueError as e:
            if value == "unknown":
                continue
            raise e


    # this test assumes that we are running on x86_64 architecture
    assert (
        get_current_platform().architecture == Arch.X86_64
    )  # Example assertion, adjust as needed
