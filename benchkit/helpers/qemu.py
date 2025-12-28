# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from enum import Enum
import pathlib
import shutil
import subprocess
from typing import Callable, List

import benchkit
from benchkit.communication import CommunicationLayer
from benchkit.communication.pty import PTYCommLayer, PTYException
from benchkit.communication.qemu import QEMUCommLayer
from benchkit.helpers.linux.initramfs import InitBuilder, InitramFS
from benchkit.helpers.linux.utilities import default_busybox

import os, fcntl, termios, time, select

from benchkit.utils import git
from benchkit.utils.types import PathType, SplitCommand


# FIXME use the proper PathType
QEMU_ARTIFACTS: pathlib.Path = pathlib.Path(".qemu_artifacts") # where to put the files that are used to build qemu

class QEMUException(Exception):
    pass

def mount():
    pass

class MountPoint:
    def __init__(
            self,
            what: PathType,
            where: PathType,
            _type: str = "ext4",
            args: List[str] = list(), # additional arguments
    ):
       self._what: PathType = what
       self._where: PathType = where
       self._type: str = _type
       self._args: List[str] = args


    @property
    def mount_cmd(self) -> List[str]:
        return ["mount", "-t", str(self._type), str(self._what), str(self._where)] + self._args

    @property
    def unmount_cmd(self) -> List[str]:
        return ["umount", str(self._where)] + self._args


# NOTE fill ad_hoc
class Arch(Enum):
    x86 = "qemu-system-x86_64"


class QEMU():
    def __init__(
            self,
            number_of_cpus: int,
            memory: int,
            kernel: PathType,
            shared_dir: PathType | None,
            enable_pty: bool, 
            utilities: Callable[[PathType], PathType] = default_busybox, # function that returns to the stuff that should go in /bin 
            mounts: list[MountPoint] = list(),
            clean_build: bool = False, # by default, we cache our artifacts
            target_arch: Arch = Arch.x86,
            artifacts_dir: PathType = QEMU_ARTIFACTS,
    ):

        # TODO check if cpio and stuff is installed on system

        self._number_of_cpus: int
        self._memory: int

        self._artifacts_dir: pathlib.Path = pathlib.Path(artifacts_dir)

        self._mounts: List[MountPoint] = mounts
        self.initrd_args: List[str] = list()
        self._kernel: PathType = kernel
        self._target_arch: Arch = target_arch

        self._extra_args: List[str] = list()
        self.shared_dir: PathType | None = shared_dir
        if shared_dir is not None:
            # TODO if interested, abstract virtfs into a file system class node
            self._extra_args.extend(["-virtfs", f"local,path={shared_dir},mount_tag=host0,security_model=none"])
            self._mounts.append(MountPoint(what=shared_dir, where="/host", _type="9p", args=["trans=virtio"]))

        if enable_pty:
            self._extra_args.extend(["-serial", "pty"])
            self._extra_args.extend(["-append", '"console=ttyS0"'])

        try:
            if clean_build:
                shutil.rmtree(self._artifacts_dir)
            os.mkdir(self._artifacts_dir)
        except FileExistsError:
            #try:
            #    os.remove(self._artifacts_dir / "initramfs.cpio.gz")
            #except FileNotFoundError:
            #    pass
            try:
                os.remove(self._artifacts_dir / "init")
            except FileNotFoundError:
                pass
        except Exception:
            raise Exception("mkdir problem") # TODO make it less retarded

        self.initramfs: InitramFS = InitramFS(cwd=self._artifacts_dir)
        self.initramfs.prepare(utilities(self._artifacts_dir))
        self.init: InitBuilder = InitBuilder()

        self._qemu_pty: None | PTYCommLayer = None
        self._qemu_term: None | QEMUCommLayer = None

    def get_pty(self):
        if self._qemu_term is not None and (port := self._qemu_term.get_pty_port()) is not None:
            self._qemu_pty = PTYCommLayer(port=port)
            return self._qemu_pty
        else:
            raise QEMUException("The QEMU machine is not running") 
    
    def add_minimal_mount_points(self):
        self._mounts.append(MountPoint(what="devtmpfs", _type="devtmpfs", where="/dev"))
        self._mounts.append(MountPoint(what="none", _type="proc", where="/proc"))
        self._mounts.append(MountPoint(what="none", _type="sysfs", where="/sys"))

    def add_mount_point(self,mount_point: MountPoint):
        self._mounts.append(mount_point)

    def _run(self):
        if self._artifacts_dir.exists():
            for mount_points in self._mounts:
                self.init.add_command(" ".join(mount_points.mount_cmd))

            self.init.build(pathlib.Path(self.initramfs.fs_path) / "init")
            # self.initrd_args.append(str(self.initramfs.compress()))
            self.initrd_args += ["build/initramfs.cpio.gz"]

            cmd: List[str] = [self._target_arch.value]
            cmd.extend([f"-kernel", str(self._kernel)])
            cmd.extend([f"-initrd", *self.initrd_args, "-nographic"])

            cmd.extend(self._extra_args)

            self._qemu_term = QEMUCommLayer(command=cmd)
        else:
            raise QEMUException("No artifacts dir")

    def __enter__(self):
        self._run()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        # TODO ask someone what is the correct procedure here
        if exception_type is not None:
            print(f"Exception: {exception_type.__name__}: {exception_value}")

        # this basically should always be True
        if self._qemu_term is not None:
            self._qemu_term.kill()
        # set_tracing_on(tracing_on=False, comm_layer=self.comm_layer)
