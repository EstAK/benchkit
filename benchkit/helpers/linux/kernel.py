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

from typing import Iterable, Self
from dataclasses import dataclass, field

from benchkit.helpers.arch import Arch
from benchkit.helpers.kconfig import KConfig, KConfigRHS
from benchkit.helpers.version import SemanticVersion, LinuxVersion
from benchkit.helpers.linux.build import (
    KernelEntry,
    LinuxBuild,
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
    # private
    __patches: list[Patch] = field(default_factory=list)
    __source_dir: pathlib.Path | None = None

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
    ) -> Self:
        kernel: Self = Kernel(
            version=Kernel.latest_version(moniker=moniker),
            platform=platform,
        )

        if download:
            kernel.download(build_dir=build_dir)

        return kernel

    def download(
        self,
        build_dir: pathlib.Path,
        clean: bool = False,
    ) -> Self:
        """
        Download the kernel source code.
        """

        base: str = f"linux-{self.version.major}.{self.version.minor}"
        tar: str = f"{base}.tar.xz"
        link: str = (
            f"https://cdn.kernel.org/pub/linux/kernel/v{self.version.major}.x/{tar}"
        )

        self.__source_dir = build_dir / base
        tar_path: pathlib.Path = build_dir / tar

        if not self.platform.comm.path_exists(build_dir):
            self.platform.comm.makedirs(str(build_dir))

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

        if not self.platform.comm.path_exists(self.__source_dir) or clean:
            # FIXME there is no explicit error handling with remove therefore, this construct is required
            if self.platform.comm.path_exists(self.__source_dir):
                self.platform.comm.remove(str(self.__source_dir), recursive=True)

            self.platform.comm.shell(
                command=[
                    "tar",
                    "-C",
                    str(build_dir),
                    "-xvf",
                    str(tar_path),
                ]
            )

        return self

    def add_patch(
        self,
        patch_file: pathlib.Path,
        pnum: int | None = None,
    ) -> Self:
        """
        Add a patch to the kernel.
        """

        # FIXME this does not really work, auto detect gives a None
        resolved_pnum: int = pnum or Patch.detect_patch_level(
            prefix=self.__source_dir.stem,
            patch_file=patch_file,
            platform=self.platform,
        )

        patch = Patch(
            patch_file=patch_file,
            cwd=self.__source_dir,  # assuming patches are applied from the parent dir
            platform=self.platform,
            pnum=resolved_pnum,
        )

        if patch.is_applied():
            print(f"Patch {patch_file} is already applied, skipping.")
        else:
            self._patches.append(patch)

        return self

    def add_patches(
        self,
        patches: Iterable[pathlib.Path],
        pnum: int | None = None,
    ) -> Self:
        """
        Add multiple patches to the kernel.
        """

        for pf in patches:
            self.add_patch(patch_file=pf, pnum=pnum)

        return self

    def distclean(self) -> None:
        """
        Clean the kernel source tree.
        """

        self.platform.comm.shell(
            command=["make", "distclean"],
            current_dir=self.__source_dir,
        )

    def compile(self) -> None:
        """
        Compile the kernel.
        """

        nb_cpus: int = int(self.platform.comm.shell("nproc"))
        self.platform.comm.shell(
            command=[
                "make",
                f"-j{nb_cpus}",
            ],
            current_dir=self.__source_dir,
        )

    def apply_patches(self) -> Self:
        """
        Apply the patches to the kernel.
        """

        for patch in self.__patches:
            patch.apply()

        return self

    def make_defconfig(self, arch: Arch | None = None) -> None:
        """
        Get the default kernel configuration.
        """

        arch: Arch = arch or Arch._platform.architecture()
        self.platform.comm.shell(
            command=["make", f"ARCH={arch.value}", "defconfig"],
            current_dir=self.__source_dir,
        )

        self.config = KConfig.from_file(
            path=self.__source_dir / ".config", platform=self.platform
        )

    def load_existing_config(self) -> None:
        """
        Load an existing kernel configuration from the source directory.
        """
        config_file: pathlib.Path = self.__source_dir / ".config"

        if not config_file.exists():
            raise Exception(f"kernel config file {config_file} does not exist")

        self.config = KConfig.from_file(
            path=config_file,
            platform=self.platform,
        )

    def update_config(self, updates: dict[str, KConfigRHS]) -> None:
        self.config.entries.update(updates)

    def save_config(self) -> None:
        self.config.write_to_file(
            out=self.__source_dir / ".config",
            platform=self.platform,
        )

        # logging.info("Cleaning the .config")
        # if subprocess.run(["make", "distclean"], cwd=base_path).returncode != 0:
        #     raise Exception("failed to make the default config")

        # logging.info("Making the default .config")
        # if subprocess.run(["make", "defconfig"], cwd=base_path).returncode != 0:
        #     raise Exception("failed to make the default config")

        # logging.info("Modifying the defconfig")
        # dot_config: DotConfig = DotConfig(path=base_path / ".config")

        # for k, v in CONFIGS.items():
        #     dot_config.set_option(option=k, value=v)

        # for conf in DISABLED_CONFIG:
        #     dot_config.unset_option(option=conf)
        # logging.info("Finished make defconfig")

        # logging.info("Starting Compilation")
        # make_cmd: List[str] = [
        #     "make",
        #     f"-j{multiprocessing.cpu_count()}",
        #     f"ARCH={arch.arch}",
        # ]
        # if subprocess.run(make_cmd, cwd=base_path).returncode != 0:
        #     raise Exception("failed to compile the kernel")
        # logging.info("Finished compiling")

        # shutil.copy2(
        #     src=str(base_path / "arch" / arch.arch / "boot" / "bzImage"),
        #     dst=str(out_dir / "bzImage"),
        # )


# class GitKernel(Kernel):
#     """Represent a Linux kernel that is to be cloned from git."""

#     def __init__(
#         self,
#         suffix: str,
#         grub_menu_id: str,
#         description: str,
#         patches: Iterable[KernelPatch],
#         repo_path: PathType,
#         repo_url: str | None = None,  # commit ID or branch
#         ref: str | None = None,
#         config_enables: List[Option] = (),
#         config_disables: List[Option] = (),
#         config_setstrings: Dict[Option, str] | None = None,
#         config_modules: List[Option] = (),
#     ):
#         super().__init__(
#             suffix=suffix,
#             grub_menu_id=grub_menu_id,
#             description=description,
#             patches=patches,
#         )
#         self._repo_path = pathlib.Path(repo_path)
#         self._repo_url = repo_url
#         self._ref = ref

#         self._config_enables = config_enables
#         self._config_disables = config_disables
#         self._config_setstrings = config_setstrings
#         self._config_modules = config_modules

#         self._lb = None

#     @property
#     def git(self) -> LinuxBuild:
#         """Instantiate and get Linux build from the git repository.

#         Returns:
#             _type_: get Linux build from the git repository.
#         """
#         if self._lb is None:
#             self._lb = LinuxBuild.from_git(
#                 repo_path=self._repo_path,
#                 repo_url=self._repo_url,
#                 ref=self._ref,
#             )
#         return self._lb

#     def cleanup(self) -> None:
#         """Cleanup the git repository by removing all changes."""
#         shell_out("git clean -fdx", current_dir=self._repo_path)
#         shell_out("git reset --hard", current_dir=self._repo_path)

#     def apply_patches(self) -> None:
#         """Apply the patches given in the constructor."""
#         for patch in self._patches:
#             self.git.apply_patch(patch_pathname=patch.filename)

#     def configure(
#         self,
#         config_enables: List[Option] = (),
#         config_disables: List[Option] = (),
#         config_setstrings: Dict[Option, str] | None = None,
#         config_modules: List[Option] = (),
#     ) -> None:
#         """Configure the build of the git kernel.

#         Args:
#             config_enables (List[Option], optional):
#                 Configure a list of kernel options to enable. Defaults to ().
#             config_disables (List[Option], optional):
#                 Configure a list of kernel options to disable. Defaults to ().
#             config_setstrings (Dict[Option, str] | None, optional):
#                 Configure a set of key-value for string kernel options. Defaults to None.
#             config_modules (List[Option], optional):
#                 Configure a list of kernel options to be built as kernel modules. Defaults to ().
#         """
#         configure_standard_kernel(linux_build=self.git)
#         self.git.configure_local_version(local_version_name=self.suffix)
#         self.git.configure_options(
#             config_enables=self._config_enables,
#             config_disables=self._config_disables,
#             config_setstrings=self._config_setstrings,
#             config_modules=self._config_modules,
#         )
#         self.git.configure_options(
#             config_enables=config_enables,
#             config_disables=config_disables,
#             config_setstrings=config_setstrings,
#             config_modules=config_modules,
#         )
#         self.git.finish_config()

#     def make(self) -> None:
#         """Build the git kernel."""
#         self.git.make()

#     def install(self) -> None:
#         """Install the git kernel."""
#         self.git.install()
#         self.git.install_cpupower()
#         self.git.install_perf()

#     def patch_config_build_install(
#         self,
#         config_enables: List[Option] = (),
#         config_disables: List[Option] = (),
#         config_setstrings: Dict[Option, str] | None = None,
#         config_modules: List[Option] = (),
#     ) -> None:
#         """Patch, configure, build and install the git kernel.

#         Args:
#             config_enables (List[Option], optional):
#                 Configure a list of kernel options to enable. Defaults to ().
#             config_disables (List[Option], optional):
#                 Configure a list of kernel options to disable. Defaults to ().
#             config_setstrings (Dict[Option, str] | None, optional):
#                 Configure a set of key-value for string kernel options. Defaults to None.
#             config_modules (List[Option], optional):
#                 Configure a list of kernel options to be built as kernel modules. Defaults to ().
#         """
#         self.cleanup()
#         self.apply_patches()
#         self.configure(
#             config_enables=config_enables,
#             config_disables=config_disables,
#             config_setstrings=config_setstrings,
#             config_modules=config_modules,
#         )
#         self.make()
#         self.install()

#     def get_grub_kernel_entry(
#         self,
#         boot_menu_desc: str,
#         isolate_all_cpus: bool,
#     ) -> KernelEntry:
#         """Get the kernel entry in the Grub menu associated with the git kernel.

#         Args:
#             boot_menu_desc (str): _description_
#             isolate_all_cpus (bool): _description_

#         Returns:
#             KernelEntry: _description_
#         """
#         return self.git.get_grub_kernel_entry(
#             menu_id=self.grub_menu_id,
#             menu_name=f"Custom Ubuntu, {boot_menu_desc}, {self._get_tag()}, {self.description}",
#             isolate_all_cpus=isolate_all_cpus,
#         )

#     def _get_tag(self) -> str:
#         kernel_tag = shell_out("git describe", current_dir=self._repo_path).strip()
#         return kernel_tag
