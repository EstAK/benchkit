# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.helpers.linux.kernel import DotConfig
from benchkit.utils.types import PathType
from benchkit.utils.git import clone_repo

from typing import List

import pathlib
import subprocess


def default_busybox(cwd: PathType) -> PathType:
    busybox_path: pathlib.Path = pathlib.Path(cwd) / "busybox"

    if not busybox_path.exists():
        clone_repo(repo_url="git://busybox.net/busybox.git", repo_src_dir=busybox_path)

    busybox_bins: pathlib.Path = busybox_path / "_install"
    if not busybox_bins.exists():
        # build busybox if not already done
        subprocess.run(["make", "defconfig"], cwd=busybox_path)

        # "patching" the config
        dot_config = DotConfig(path=busybox_path / ".config")
        dot_config.unset_option("CONFIG_TC")
        dot_config.set_option("CONFIG_STATIC", "y")

        subprocess.run(["make", "-j", "$(npproc)"], cwd=busybox_path)

    return busybox_bins


class MountPoint:
    def __init__(
        self,
        what: PathType,
        where: PathType,
        type_: str = "ext4",
        mount_args: List[str] = list(),  # additional arguments
        umount_args: List[str] = list(),  # additional arguments
    ):
        self._what: PathType = what
        self._where: PathType = where
        self._type: str = type_
        self._mount_args: List[str] = mount_args
        self._umount_args: List[str] = umount_args

    @property
    def mount_cmd(self) -> List[str]:
        return [
            "mount",
            "-t",
            str(self._type),
            str(self._what),
            str(self._where),
        ] + self._mount_args

    @property
    def unmount_cmd(self) -> List[str]:
        return ["umount", str(self._where)] + self._umount_args
