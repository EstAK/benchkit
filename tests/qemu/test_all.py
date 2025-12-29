#!/usr/bin/env python3
# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.helpers.qemu import QEMUConfig
from benchkit.helpers.linux.initramfs import InitBuilder
from benchkit.helpers.cpu import CPUTopology

import pathlib


if __name__ == "__main__":
    if not pathlib.Path("build").exists():
        print("This test assumes that a build directory is pre-made for QEMU")
        exit(1)

    qemu_config = QEMUConfig(
        cpu_topology=CPUTopology(nb_cores=4, nb_threads_per_core=2),
        memory=4069,
        kernel=pathlib.Path("./build/bzImage"),
        shared_dir="shared",
        enable_pty=True,
        artifacts_dir="./build",
        clean_build=False,
    )

    # qemu_config.isolcpus([1, 4])
    qemu_config.init = InitBuilder.default()


    with qemu_config.spawn() as qemu:
        with qemu.open_pty() as pty:
            str_ = pty.shell(command="ls")

        # qemu.shell(command="help")


