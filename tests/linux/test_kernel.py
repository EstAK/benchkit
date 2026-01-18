#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

import os
import pathlib

from benchkit.helpers.arch import Arch
from benchkit.helpers.linux.kernel import Kernel, Moniker
from benchkit.helpers.version import LinuxVersion

if __name__ == "__main__":
    # this cannot be tested reliably as the versions are always changing
    stable_ver: LinuxVersion = (
        Kernel.latest_version(moniker=Moniker.STABLE)
        if not (pathlib.Path("build") / "linux-6.18.tar.xz").exists()
        else LinuxVersion.from_str("6.18")
    )
    out_dir: pathlib.Path = pathlib.Path("build")

    if not out_dir.exists():
        os.mkdir(out_dir)

    kernel: Kernel = Kernel.download_source(
        version=stable_ver,
        out_dir=pathlib.Path("build"),
    )

    kernel.make_defconfig(arch=Arch.X86)
    kernel.compile()
