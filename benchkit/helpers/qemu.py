# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
import shutil
import os
import subprocess

from typing import Callable, List, Never
from enum import Enum

from benchkit.helpers.linux.utilities import default_busybox, MountPoint
from benchkit.helpers.linux.initramfs import InitBuilder, InitramFS
from benchkit.communication.qemu import QEMUCommLayer
from benchkit.helpers.cpu import CPUTopology
from benchkit.utils.types import PathType


QEMU_ARTIFACTS: pathlib.Path = pathlib.Path(
    ".qemu_artifacts"
)  # where to put the files that are used to build qemu

def assert_never(arg: Never) -> Never:
    raise AssertionError("Expected code to be unreachable")

class QEMUConfigException(Exception):
    pass


# NOTE fill ad_hoc
class QEMUSystem(Enum):
    x86_64 = "qemu-system-x86_64"

    @property
    def arch(self) -> str:
        match self:
            case QEMUSystem.x86_64:
                return "x86_64"
            case _:
                assert_never(self)


# NOTE fill ad_hoc
class Accellerator(Enum):
    kvm = "kvm"
    tcg = "tcg"


class QEMUConfig:
    def __init__(
        self,
        cpu_topology: CPUTopology,
        memory: int,
        kernel: PathType,
        shared_folder: PathType | None,
        enable_pty: bool,
        accel: Accellerator | None = None,
        max_cpus: int | None = None,
        kernel_args: List[str] = [],
        utilities: Callable[
            [PathType], PathType
        ] = default_busybox,  # function that returns to the stuff that should go in the initramfs
        mounts: list[MountPoint] = list(),
        clean_build: bool = False,  # by default, we cache our artifacts
        target_arch: QEMUSystem = QEMUSystem.x86_64,
        artifacts_dir: PathType = QEMU_ARTIFACTS,
        nb_threads_per_core: int = 2,
    ):
        # TODO check if cpio and stuff is installed on system

        self._cpu_topology: CPUTopology = cpu_topology
        self._guest_logical_cores = (
            self._cpu_topology.nb_cores
            * self._cpu_topology.nb_sockets
            * self._cpu_topology.nb_threads_per_core
        )
        # by default the maximum number of cpus that can be hot plugged is the
        # the same as the number of guest logical cores
        if max_cpus is None:
            self._max_cpus: int = self._guest_logical_cores
        elif max_cpus >= self._guest_logical_cores:
            self._max_cpus = max_cpus
        else:
            raise QEMUConfigException(
                "The maximum of CPUs is fewer than the number of CPUs allocated to the machine"
            )
        self._accel = accel

        self._memory: int = memory
        self._clean_build: bool = clean_build

        self._artifacts_dir: pathlib.Path = pathlib.Path(artifacts_dir)

        self._mounts: List[MountPoint] = mounts
        self._initrd_args: List[str] = list()
        self._kernel: PathType = kernel
        self._kernel_args: List[str] = [] + kernel_args
        self._target_arch: QEMUSystem = target_arch

        self._extra_args: List[str] = list()
        self._shared_folder: MountPoint | None = None
        # TODO if interested, abstract fs into its own class ?
        if shared_folder is not None:
            self._shared_folder = MountPoint(
                what=shared_folder,
                where="/mnt",
                type_="9p",
                mount_args=["trans=virtio"],
            )

            if not self._shared_folder._what:
                os.mkdir(self._shared_folder._what)

            self._extra_args.extend(
                [
                    "-virtfs",
                    f"local,path={self._shared_folder._what},mount_tag={self._shared_folder._what},security_model=none",
                ]
            )
        # FIXME fix ad hoc with other comm layers to QEMU
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

    @staticmethod
    def supported_accelerators(arch: QEMUSystem) -> List[Accellerator]:
        cmd: List[str] = [arch.value, "-accel", "help"]
        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return [Accellerator(x) for x in ret.stdout.decode().split("\n")[1::] if x]

    # NOTE this should probably move to a Linux Kernel config class in the future
    def isolcpus(self, cpus: List[int]):
        self._cpu_topology.isolated_cores.union(cpus)

    def add_minimal_mount_points(self):
        self._mounts.append(MountPoint(what="devtmpfs", type_="devtmpfs", where="/dev"))
        self._mounts.append(MountPoint(what="none", type_="proc", where="/proc"))
        self._mounts.append(MountPoint(what="none", type_="sysfs", where="/sys"))

    def add_mount_point(self, mount_point: MountPoint):
        self._mounts.append(mount_point)

    def spawn(self) -> QEMUCommLayer:
        if self._artifacts_dir.exists():
            if self._shared_folder is not None:
                self._mounts.append(self._shared_folder)

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
                    ",".join(
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

            if self._accel is not None:
                cmd.extend(["-accel", self._accel.value])

            cmd.extend(["-m", str(self._memory)])
            cmd.extend(["-kernel", str(self._kernel)])
            cmd.extend(["-initrd", *self._initrd_args])
            cmd.append("-nographic")

            self._kernel_args.append(
                f"isolcpus={','.join([cpu for cpu in self._cpu_topology.isolated_cores])}"
            )
            cmd.extend(["-append", f'"{" ".join(self._kernel_args)}"'])

            cmd.extend(self._extra_args)
            print(" ".join(cmd))

            return QEMUCommLayer(command=cmd, shared_folder=self._shared_folder)
        else:
            raise QEMUConfigException("No artifacts dir")
