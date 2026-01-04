# Copyright (C) 2023 Huawei Technologies Co., Ltd. All rights reserved.
# SPDX-License-Identifier: MIT
"""
Instantiate kernels, in particular from git, and manage the whole build process, including patching,
configuring, compiling and installing.
"""

import pathlib
from typing import Dict, Iterable, List

from benchkit.communication.generic import CommunicationLayer
from benchkit.helpers.linux.build import (
    KernelEntry,
    LinuxBuild,
    Option,
    configure_standard_kernel,
)
from benchkit.helpers.version import SemanticVersion
from benchkit.shell.shell import shell_out
from benchkit.utils.types import PathType


class KernelPatch:
    """Represent a patch that can be applied on a Linux kernel."""

    def __init__(self, filename: PathType):
        self.filename = pathlib.Path(filename)


class Kernel:
    """Represent a Linux kernel."""

    def __init__(
        self,
        suffix: str,
        grub_menu_id: str,
        description: str,
        patches: Iterable[KernelPatch],
    ):
        self.suffix = suffix
        self.grub_menu_id = grub_menu_id
        self.description = description
        self._patches = patches


class GitKernel(Kernel):
    """Represent a Linux kernel that is to be cloned from git."""

    def __init__(
        self,
        suffix: str,
        grub_menu_id: str,
        description: str,
        patches: Iterable[KernelPatch],
        repo_path: PathType,
        repo_url: str | None = None,  # commit ID or branch
        ref: str | None = None,
        config_enables: List[Option] = (),
        config_disables: List[Option] = (),
        config_setstrings: Dict[Option, str] | None = None,
        config_modules: List[Option] = (),
    ):
        super().__init__(
            suffix=suffix,
            grub_menu_id=grub_menu_id,
            description=description,
            patches=patches,
        )
        self._repo_path = pathlib.Path(repo_path)
        self._repo_url = repo_url
        self._ref = ref

        self._config_enables = config_enables
        self._config_disables = config_disables
        self._config_setstrings = config_setstrings
        self._config_modules = config_modules

        self._lb = None

    @property
    def git(self) -> LinuxBuild:
        """Instantiate and get Linux build from the git repository.

        Returns:
            _type_: get Linux build from the git repository.
        """
        if self._lb is None:
            self._lb = LinuxBuild.from_git(
                repo_path=self._repo_path,
                repo_url=self._repo_url,
                ref=self._ref,
            )
        return self._lb

    def cleanup(self) -> None:
        """Cleanup the git repository by removing all changes."""
        shell_out("git clean -fdx", current_dir=self._repo_path)
        shell_out("git reset --hard", current_dir=self._repo_path)

    def apply_patches(self) -> None:
        """Apply the patches given in the constructor."""
        for patch in self._patches:
            self.git.apply_patch(patch_pathname=patch.filename)

    def configure(
        self,
        config_enables: List[Option] = (),
        config_disables: List[Option] = (),
        config_setstrings: Dict[Option, str] | None = None,
        config_modules: List[Option] = (),
    ) -> None:
        """Configure the build of the git kernel.

        Args:
            config_enables (List[Option], optional):
                Configure a list of kernel options to enable. Defaults to ().
            config_disables (List[Option], optional):
                Configure a list of kernel options to disable. Defaults to ().
            config_setstrings (Dict[Option, str] | None, optional):
                Configure a set of key-value for string kernel options. Defaults to None.
            config_modules (List[Option], optional):
                Configure a list of kernel options to be built as kernel modules. Defaults to ().
        """
        configure_standard_kernel(linux_build=self.git)
        self.git.configure_local_version(local_version_name=self.suffix)
        self.git.configure_options(
            config_enables=self._config_enables,
            config_disables=self._config_disables,
            config_setstrings=self._config_setstrings,
            config_modules=self._config_modules,
        )
        self.git.configure_options(
            config_enables=config_enables,
            config_disables=config_disables,
            config_setstrings=config_setstrings,
            config_modules=config_modules,
        )
        self.git.finish_config()

    def make(self) -> None:
        """Build the git kernel."""
        self.git.make()

    def install(self) -> None:
        """Install the git kernel."""
        self.git.install()
        self.git.install_cpupower()
        self.git.install_perf()

    def patch_config_build_install(
        self,
        config_enables: List[Option] = (),
        config_disables: List[Option] = (),
        config_setstrings: Dict[Option, str] | None = None,
        config_modules: List[Option] = (),
    ) -> None:
        """Patch, configure, build and install the git kernel.

        Args:
            config_enables (List[Option], optional):
                Configure a list of kernel options to enable. Defaults to ().
            config_disables (List[Option], optional):
                Configure a list of kernel options to disable. Defaults to ().
            config_setstrings (Dict[Option, str] | None, optional):
                Configure a set of key-value for string kernel options. Defaults to None.
            config_modules (List[Option], optional):
                Configure a list of kernel options to be built as kernel modules. Defaults to ().
        """
        self.cleanup()
        self.apply_patches()
        self.configure(
            config_enables=config_enables,
            config_disables=config_disables,
            config_setstrings=config_setstrings,
            config_modules=config_modules,
        )
        self.make()
        self.install()

    def get_grub_kernel_entry(
        self,
        boot_menu_desc: str,
        isolate_all_cpus: bool,
    ) -> KernelEntry:
        """Get the kernel entry in the Grub menu associated with the git kernel.

        Args:
            boot_menu_desc (str): _description_
            isolate_all_cpus (bool): _description_

        Returns:
            KernelEntry: _description_
        """
        return self.git.get_grub_kernel_entry(
            menu_id=self.grub_menu_id,
            menu_name=f"Custom Ubuntu, {boot_menu_desc}, {self._get_tag()}, {self.description}",
            isolate_all_cpus=isolate_all_cpus,
        )

    def _get_tag(self) -> str:
        kernel_tag = shell_out("git describe", current_dir=self._repo_path).strip()
        return kernel_tag


def get_version(
    comm_layer: CommunicationLayer,
) -> SemanticVersion:
    command: List[str] = ["uname", "-r"]
    major, minor, patch = map(
        lambda a: int(a),
        comm_layer.shell(
            command=command,
            print_input=False,
            print_output=False,
        )
        .strip()
        .split("."),
    )

    return SemanticVersion(major=major, minor=minor, patch=patch)


class NotAnOptionException(Exception):
    pass


class DotConfig:
    """
    Dot config files abstraction
    """

    def __init__(self, path: PathType):
        self._path = path

    @property
    def enabled_options(self):
        acc: list[str] = list()
        with open(self._path, "r") as file:
            for line in file:
                if "=" in line:
                    acc.append(line.split("=")[0])
        return acc

    def _matches_option(self, line: str, option: str) -> bool:
        return line.startswith(f"{option}=") or line.startswith(
            f"# {option} is not set"
        )

    def set_option(self, option: str, value: str):
        with open(self._path, "r") as file:
            lines = file.readlines()

        found = False
        for i, line in enumerate(lines):
            if self._matches_option(line, option):
                lines[i] = f"{option}={value}\n"
                found = True
                break

        if not found:
            lines.append(f"{option}={value}\n")

        with open(self._path, "w") as file:
            file.writelines(lines)

    def get_option(self, option: str) -> str | None:
        with open(self._path, "r") as file:
            for line in file:
                if line.startswith(f"{option}="):
                    return line.split("=", 1)[1].strip()
                if line.startswith(f"# {option} is not set"):
                    return None

    def unset_option(self, option: str):
        with open(self._path, "r") as file:
            lines = file.readlines()

        found = False
        for i, line in enumerate(lines):
            if self._matches_option(line, option):
                lines[i] = f"# {option} is not set\n"
                found = True
                break

        if not found:
            raise NotAnOptionException(f"The option {option} does not exist")

        with open(self._path, "w") as file:
            file.writelines(lines)
