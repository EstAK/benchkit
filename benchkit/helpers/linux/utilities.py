# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.helpers.linux.kernel import DotConfig
from benchkit.utils import git
from benchkit.utils.types import PathType

import pathlib
import subprocess


def default_busybox(cwd: PathType) -> PathType:

    busybox_path: pathlib.Path = pathlib.Path(cwd) / "busybox"

    if not busybox_path.exists():
        git.clone_repo(repo_url="git://busybox.net/busybox.git", repo_src_dir=busybox_path)

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
