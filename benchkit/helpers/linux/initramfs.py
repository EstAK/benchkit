# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from benchkit.helpers.linux.utilities import MountPoint
from benchkit.utils.types import PathType

import subprocess
import pathlib
import shutil
import stat
import os

from typing import List, Self


class InitBuilder:
    def __init__(
        self,
        shebang: str = "#!/bin/sh",
        footer: str = "exec /bin/sh",
    ) -> None:
        self.shebang: str = shebang
        self.footer: str = footer

        # I am not right about this being the correct type for a command
        self.commands: List[str] = list()

    @staticmethod
    def default() -> Self:
        init = InitBuilder()

        init.add_command(
            " ".join(
                MountPoint(what="devtmpfs", where="/dev", type_="devtmpfs").mount_cmd
            )
        )
        init.add_command(
            " ".join(MountPoint(what="none", where="/proc", type_="proc").mount_cmd)
        )
        init.add_command(
            " ".join(MountPoint(what="none", where="/sys", type_="sysfs").mount_cmd)
        )

        return init

    def add_command(self, command: str):
        # NOTE can I abstract the command ?
        self.commands.append(command)

    def build(self, out: PathType):
        """
        Builds the init file at out
        """
        with open(out, "w") as file:
            file.writelines(
                map(
                    lambda line: line + "\n",
                    [
                        self.shebang,
                        *self.commands,
                        self.footer,
                    ],
                )
            )

        os.chmod(path=out, mode=os.stat(out).st_mode | stat.S_IXUSR)


class InitramFS:
    def __init__(self, cwd: PathType) -> None:
        self._cwd: PathType = cwd
        self.fs_path: PathType = pathlib.Path(cwd) / "initramfs"

    def prepare(
        self,
        utils: PathType | None,
    ):
        initramfs_folder: pathlib.Path = pathlib.Path(self.fs_path)

        try:
            shutil.rmtree(initramfs_folder)
        except FileNotFoundError:
            pass

        os.mkdir(initramfs_folder)
        os.mkdir(initramfs_folder / "tmp")
        os.mkdir(initramfs_folder / "bin")
        os.mkdir(initramfs_folder / "mnt")
        os.mkdir(initramfs_folder / "sbin")
        os.mkdir(initramfs_folder / "etc")
        os.mkdir(initramfs_folder / "proc")
        os.mkdir(initramfs_folder / "sys")
        os.mkdir(initramfs_folder / "dev")

        os.mkdir(initramfs_folder / "usr")
        os.mkdir(initramfs_folder / "usr" / "bin")
        os.mkdir(initramfs_folder / "usr" / "sbin")
        os.mkdir(initramfs_folder / "usr" / "local")
        os.mkdir(initramfs_folder / "usr" / "local" / "bin")

        if utils is not None:
            for item in pathlib.Path(utils).iterdir():
                target: pathlib.Path = initramfs_folder / item.name

                if item.is_dir():
                    shutil.copytree(
                        item,
                        target,
                        symlinks=True,
                        dirs_exist_ok=True,
                    )
                else:
                    shutil.copy2(
                        item,
                        target,
                        follow_symlinks=False,
                    )

    def compress(
        self,
        preserve_uncompressed: bool = False,
    ) -> PathType:
        initramfs_folder: pathlib.Path = pathlib.Path(self.fs_path)
        compressed_initramfs: str = "initramfs.cpio.gz"
        subprocess.run(
            f"find . -print0 | cpio --null -ov --format=newc | gzip -9 > ../{compressed_initramfs}",
            cwd=pathlib.Path(self._cwd) / "initramfs",
            shell=True,
            check=True,
        )

        if not preserve_uncompressed:
            shutil.rmtree(initramfs_folder)

        return pathlib.Path(self._cwd) / compressed_initramfs
