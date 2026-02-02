# Copyright (C) 2023 Huawei Technologies Co., Ltd. All rights reserved.
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT
"""
Instantiate kernels, in particular from git, and manage the whole build process, including patching,
configuring, compiling and installing.
"""

import pathlib
import json
import enum

from typing import Iterable, Self, Callable
from dataclasses import dataclass, field

from benchkit.helpers.arch import Arch
from benchkit.helpers.kconfig import KConfig, KConfigRHS
from benchkit.helpers.version import SemanticVersion, LinuxVersion
from benchkit.helpers.linux.build import (
    KernelEntry,
    # LinuxBuild,
    Option,
    configure_standard_kernel,
)
from benchkit.shell.shell import shell_out
from benchkit.utils.types import PathType
from benchkit.platforms import get_current_platform, Platform
from benchkit.helpers.patch import Patch


class Moniker(enum.Enum):
    MAINLINE = "mainline"
    STABLE = "stable"
    LTS = "longterm"


@dataclass
class MakefileInfo:
    suffix: str
    grub_menu_id: str
    description: str


@dataclass
class Kernel:
    """
    Represent a Linux kernel.
    """

    version: LinuxVersion
    platform: Platform
    makefile_info: MakefileInfo | None = None
    config: KConfig | None = None

    patches: list[Patch] = field(default_factory=list)
    source_dir: pathlib.Path | None = None

    @staticmethod
    def latest_version(moniker: Moniker) -> LinuxVersion:
        platform: Platform = get_current_platform()
        file_: str = "releases.json"
        platform.comm.shell(
            command=[
                "wget",
                f"https://www.kernel.org/{file_}",
            ]
        )

        releases = json.loads(platform.comm.read_file(file_))["releases"]
        # sort by release date to get the latest per moniker as there is no
        # guarantee on order from kernel.org
        releases.sort(key=lambda r: int(r["released"]["timestamp"]))
        version: LinuxVersion | None = None

        for release in releases:
            if release["moniker"] == moniker.value:
                version = LinuxVersion.from_str(release["version"])

        platform.comm.remove(file_, recursive=False)
        if version is None:
            raise Exception("no available version")

        return version

    @staticmethod
    def latest(
        build_dir: pathlib.Path,
        platform: Platform,
        moniker: Moniker,
        download: bool = False,
    ) -> "Kernel":
        kernel: Kernel = Kernel(
            version=Kernel.latest_version(moniker=moniker),
            platform=platform,
        )

        if download:
            kernel.download(build_dir=build_dir)

        return kernel

    def download_arbitrary(
        self,
        build_dir: pathlib.Path,
        dl: Callable[[pathlib.Path], pathlib.Path],
    ) -> None:
        """
        Download an arbitrary kernel version.
        Args:
            build_dir (pathlib.Path): The build directory.
            dl (Callable[[pathlib.Path], pathlib.Path]): A function that takes the build directory
                and returns the path to the downloaded source directory.
        """
        self.source_dir = build_dir / dl(build_dir)

    def download(
        self,
        build_dir: pathlib.Path,
        clean: bool = False,
    ) -> None:
        """
        Download the kernel source code.
        Args:
            build_dir (pathlib.Path): The build directory.
            clean (bool): Whether to clean the source directory if it already exists.
        """

        base: str = f"linux-{self.version.major}.{self.version.minor}"
        tar: str = f"{base}.tar.xz"
        link: str = (
            f"https://cdn.kernel.org/pub/linux/kernel/v{self.version.major}.x/{tar}"
        )

        self.source_dir = build_dir / base
        tar_path: pathlib.Path = build_dir / tar

        if not self.platform.comm.path_exists(build_dir):
            self.platform.comm.makedirs(str(build_dir), exist_ok=True)

        # a tarball is assumed clean
        if not self.platform.comm.path_exists(tar_path):
            self.platform.comm.shell(
                command=[
                    "wget",
                    str(link),
                    "-O",
                    str(tar_path),
                ],
                shell=True,
            )

        if not self.platform.comm.path_exists(self.source_dir) or clean:
            # FIXME there is no explicit error handling with remove therefore, this construct is required
            if self.platform.comm.path_exists(self.source_dir):
                self.platform.comm.remove(str(self.source_dir), recursive=True)

            self.platform.comm.shell(
                command=[
                    "tar",
                    "-C",
                    str(build_dir),
                    "-xvf",
                    str(tar_path),
                ]
            )

    def add_patch(
        self,
        patch_file: pathlib.Path,
        pnum: int | None = None,
    ) -> None:
        """
        Add a patch to the kernel.
        """

        if self.source_dir is None:
            raise Exception("kernel source directory is not set, cannot add patch")

        # FIXME this does not really work, auto detect gives a None
        resolved_pnum: int = pnum or Patch.detect_patch_level(
            prefix=self.source_dir.stem,
            patch_file=patch_file,
            platform=self.platform,
        )

        patch = Patch(
            patch_file=patch_file,
            cwd=self.source_dir,  # assuming patches are applied from the parent dir
            platform=self.platform,
            pnum=resolved_pnum,
        )

        if patch.is_applied():
            print(f"Patch {patch_file} is already applied, skipping.")
        else:
            self.patches.append(patch)

    def add_patches(
        self,
        patches: Iterable[pathlib.Path],
        pnum: int | None = None,
    ) -> None:
        """
        Add multiple patches to the kernel.
        """

        for pf in patches:
            self.add_patch(patch_file=pf, pnum=pnum)

    def distclean(self) -> None:
        """
        Clean the kernel source tree.
        """

        self.platform.comm.shell(
            command=["make", "distclean"],
            current_dir=self.source_dir,
        )

    def compile(
        self,
        targets: list[str] = list(),
    ) -> None:
        """
        Compile the kernel.
        """

        # NOTE there is so much code for makefiles, should we abstract them ?
        nb_cpus: int = int(self.platform.comm.shell("nproc"))
        cmd: list[str] = [
            "make",
            f"-j{nb_cpus}",
        ]
        cmd.extend(targets)
        self.platform.comm.shell(
            command=cmd,
            current_dir=self.source_dir,
        )

    def apply_patches(self) -> None:
        """
        Apply the patches to the kernel.
        """

        for patch in self.patches:
            patch.apply()

    def make_defconfig(self, arch: Arch | None = None) -> None:
        """
        Get the default kernel configuration.
        """

        if self.source_dir is None:
            raise Exception("kernel source directory is not set, cannot make defconfig")

        _arch: Arch = arch or self.platform.architecture
        self.platform.comm.shell(
            command=["make", f"ARCH={_arch.value}", "defconfig"],
            current_dir=self.source_dir,
        )

        self.config = KConfig.from_file(
            path=self.source_dir / ".config", platform=self.platform
        )

    def load_existing_config(self) -> None:
        """
        Load an existing kernel configuration from the source directory.
        """
        if self.source_dir is None:
            raise Exception("kernel source directory is not set, cannot load config")

        config_file: pathlib.Path = self.source_dir / ".config"

        if not config_file.exists():
            raise Exception(f"kernel config file {config_file} does not exist")

        self.config = KConfig.from_file(
            path=config_file,
            platform=self.platform,
        )

    def update_config(self, updates: dict[str, KConfigRHS]) -> None:
        if self.config is None:
            raise Exception("kernel config is not loaded, cannot update config")

        self.config.entries.update(updates)

    def save_config(self) -> None:
        if self.source_dir is None or self.config is None:
            raise Exception("kernel source directory or config is not set, cannot save config")

        self.config.write_to_file(
            out=self.source_dir / ".config",
            platform=self.platform,
        )


@dataclass
class KernelBuilder:
    inner: Kernel
