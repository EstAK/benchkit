# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from enum import Enum
import pathlib
import shutil
from typing import Callable, List

from benchkit.communication import CommunicationLayer
from benchkit.communication.pty import PTYCommLayer, PTYException
from benchkit.communication.qemu import QEMUCommLayer
from benchkit.helpers.linux.initramfs import InitBuilder, InitramFS
from benchkit.helpers.linux.utilities import default_busybox, MountPoint
from benchkit.helpers.cpu import CPUTopology

import os

from benchkit.utils.types import PathType, SplitCommand


QEMU_ARTIFACTS: pathlib.Path = pathlib.Path(
    ".qemu_artifacts"
)  # where to put the files that are used to build qemu


class QEMUException(Exception):
    pass


# NOTE fill ad_hoc
class Arch(Enum):
    x86_64 = "qemu-system-x86_64"


class QEMUConfig:
    def __init__(
        self,
        cpu_topology: CPUTopology,
        guest_logical_cores: int,
        max_cpus: int,
        memory: int,
        kernel: PathType,
        shared_dir: PathType | None,
        enable_pty: bool,
        kernel_args: List[str] = [],
        utilities: Callable[
            [PathType], PathType
        ] = default_busybox,  # function that returns to the stuff that should go in the initramfs
        mounts: list[MountPoint] = list(),
        clean_build: bool = False,  # by default, we cache our artifacts
        target_arch: Arch = Arch.x86_64,
        artifacts_dir: PathType = QEMU_ARTIFACTS,
        nb_threads_per_core: int = 2,
    ):
        # TODO check if cpio and stuff is installed on system

        self._max_cpus: int = max_cpus
        self._cpu_topology: CPUTopology = cpu_topology
        self._guest_logical_cores = (
            self._cpu_topology.nb_cores
            * self._cpu_topology.nb_sockets
            * self._cpu_topology.nb_threads_per_core
        )

        self._memory: int = memory
        self._clean_build: bool = clean_build

        self._artifacts_dir: pathlib.Path = pathlib.Path(artifacts_dir)

        self._mounts: List[MountPoint] = mounts
        self._initrd_args: List[str] = list()
        self._kernel: PathType = kernel
        self._kernel_args: List[str] = [] + kernel_args
        self._target_arch: Arch = target_arch

        self._extra_args: List[str] = list()
        self.shared_dir: PathType | None = shared_dir
        if shared_dir is not None:
            # TODO if interested, abstract fs into its own class ?
            self._extra_args.extend(
                [
                    "-virtfs",
                    f"local,path={shared_dir},mount_tag=host0,security_model=none",
                ]
            )
            self._mounts.append(
                MountPoint(
                    what=shared_dir, where="/mnt", _type="9p", args=["trans=virtio"]
                )
            )

        if enable_pty:
            self._extra_args.extend(["-serial", "pty"])
            self._kernel_args.append("console=ttyS0")

        try:
            if self._clean_build and self._artifacts_dir.exists():
                shutil.rmtree(self._artifacts_dir)
            else:
                os.mkdir(self._artifacts_dir)
        except FileExistsError:
            print("re-using the previous artifacts")
        except Exception:
            raise Exception("mkdir problem")  # TODO make it less retarded

        self.initramfs: InitramFS = InitramFS(cwd=self._artifacts_dir)
        self.initramfs.prepare(utilities(self._artifacts_dir))
        self.init: InitBuilder = InitBuilder()
        self._comm_layer: QEMUCommLayer | None = None

    # NOTE this should probably move to a Linux Kernel config class in the future
    def isolcpus(self, cpus: List[int]):
        self._cpu_topology.isolated_cores.union(cpus)

    def add_minimal_mount_points(self):
        self._mounts.append(MountPoint(what="devtmpfs", _type="devtmpfs", where="/dev"))
        self._mounts.append(MountPoint(what="none", _type="proc", where="/proc"))
        self._mounts.append(MountPoint(what="none", _type="sysfs", where="/sys"))

    def add_mount_point(self, mount_point: MountPoint):
        self._mounts.append(mount_point)

    def spawn(self) -> QEMUCommLayer:
        if self._artifacts_dir.exists():
            for mount_points in self._mounts:
                self.init.add_command(" ".join(mount_points.mount_cmd))

            self.init.build(pathlib.Path(self.initramfs.fs_path) / "init")

            if (
                self._clean_build
                or not (self._artifacts_dir / "initramfs.cpio.gz").exists()
            ):
                self._initrd_args.append(str(self.initramfs.compress()))
            else:
                self._initrd_args += ["build/initramfs.cpio.gz"]

            cmd: List[str] = [self._target_arch.value]
            cmd.extend(
                [
                    "-smp",
                    *",".join(
                        [
                            str(self._guest_logical_cores),
                            f"cores={self._cpu_topology.nb_cores}",
                            f"threads={self._cpu_topology.nb_threads_per_core}",
                            f"sockets={self._cpu_topology.nb_sockets}",
                            f"maxcpus={self._max_cpus}",
                        ]
                    ),
                ]
            )
            cmd.extend(["-m", str(self._memory)])
            cmd.extend(["-kernel", str(self._kernel)])
            cmd.extend(["-initrd", *self._initrd_args])
            cmd.append("-nographic")

            self._kernel_args.append(
                f"isolcpus={','.join([cpu for cpu in self._cpu_topology.isolated_cores])}"
            )
            cmd.extend(["-append", f'"{" ".join(self._kernel_args)}"'])

            cmd.extend(self._extra_args)

            return QEMUCommLayer(command=cmd)
        else:
            raise QEMUException("No artifacts dir")
