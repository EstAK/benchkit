#!/usr/bin/env python3
# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.platforms.qemu import QEMUIntrospection, QEMUMachine

from benchkit.helpers.qemu import QEMUConfig, QEMUSystem
from benchkit.helpers.linux.initramfs import InitBuilder
from benchkit.helpers.cpu import CPUTopology

from benchkit.communication.qemu import QEMUPty

import pathlib
import subprocess


if __name__ == "__main__":
    if not pathlib.Path("build").exists():
        print("This test assumes that a build directory is pre-made for QEMU")
        exit(1)

    supported_accelerators = QEMUConfig.supported_accelerators(arch=QEMUSystem.x86_64)
    qemu_config = QEMUConfig(
        cpu_topology=CPUTopology(nb_cores=4, nb_threads_per_core=2),
        memory=4069,
        kernel=pathlib.Path("./build/bzImage"),
        shared_folder="shared",
        enable_pty=True,
        artifacts_dir="./build",
        clean_build=False,
        accel=supported_accelerators[1],
    )
    subprocess.run("echo 'hello world!' > hello.txt", shell=True)
    qemu_config.init = InitBuilder.default()

    with qemu_config.spawn() as qemu_comm:
        qemu: QEMUIntrospection = QEMUIntrospection(
            comm_layer=qemu_comm, qemu_config=qemu_config
        )
        machine: QEMUMachine[QEMUPty] = qemu.machine(comm=qemu.comm.open_pty())
        with machine.comm as pty:
            pty.copy_from_host("hello.txt", pathlib.Path("/tmp") / "world.txt")
            str_ = pty.shell(
                command="cat /tmp/world.txt", print_output=False, print_input=False
            )
            print(str_)

            # async process
