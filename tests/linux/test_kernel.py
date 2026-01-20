#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

import os
import pathlib

from benchkit.helpers.arch import Arch
from benchkit.helpers.linux.kernel import Kernel, Moniker
from benchkit.helpers.version import LinuxVersion
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    build_dir: pathlib.Path = pathlib.Path("build")

    if not build_dir.exists():
        os.mkdir(build_dir)

    kernel: Kernel = Kernel.latest(
        build_dir=build_dir,
        moniker=Moniker.LTS,
        platform=get_current_platform(),
        download=True,
    )

    kernel.make_defconfig(arch=Arch.X86)
    kernel.compile()
