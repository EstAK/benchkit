"""
This module provides classes and functions to create and manage a
Filesystem Hierarchy Standard (FHS) structure, including mount points
and an init script for mounting essential filesystems.
"""

import pathlib
import enum

from typing import Callable, Self
from dataclasses import dataclass, field

from benchkit.platforms import Platform


@dataclass
class MountPoint:
    what: pathlib.Path
    where: pathlib.Path
    fstype: str = "ext4"  # TODO make it an enum ?

    def mount_cmd(
        self,
        mount_args: list[str] = list(),
    ) -> list[str]:
        cmd: list[str] = ["mount", "-t", self.fstype]

        if mount_args:
            cmd.append("-o")
            cmd.append(",".join(mount_args))  # arguments are comma separated

        cmd.append(str(self.what))
        cmd.append(str(self.where))

        return cmd

    # REVIEW make a shellFormatter visitor to format generic abstractions into cmds ?
    def unmount_cmd(
        self,
        umount_args: list[str] = list(),
    ) -> list[str]:
        return ["umount", str(self.where)] + umount_args


# list of default mount points
PROC = MountPoint(
    what=pathlib.Path("none"),
    where=pathlib.Path("/proc"),
    fstype="proc",
)
SYS = MountPoint(
    what=pathlib.Path("none"),
    where=pathlib.Path("/sys"),
    fstype="sysfs",
)
DEV = MountPoint(
    what=pathlib.Path("none"),
    where=pathlib.Path("/dev"),
    fstype="devtmpfs",
)


MINIMAL_BASE_DIRS = list(
    map(
        lambda a: pathlib.Path(a),
        ["bin", "dev", "lib", "sbin", "proc", "sys", "usr"],
    )
)
MINIMAL_USR_DIRS = list(
    map(
        lambda a: pathlib.Path(a),
        [
            "bin",
            "sbin",
            "local",
        ],
    )
) + [pathlib.Path("local") / "bin"]


@dataclass
class FHSDirs:
    base_dirs: list[pathlib.Path] = field(
        default_factory=lambda: MINIMAL_BASE_DIRS,
    )
    user_subdirs: list[pathlib.Path] = field(default_factory=lambda: MINIMAL_USR_DIRS)

    def __contains__(self, item: object) -> bool:
        """
        Subset operation
        """
        if isinstance(item, FHSProfile):
            item = item.value

        if isinstance(item, pathlib.Path):
            return item in self.base_dirs or item in self.user_subdirs

        if isinstance(item, FHSDirs):
            for dir in item.base_dirs:
                if dir not in self.base_dirs:
                    return False
            for dir in item.user_subdirs:
                if dir not in self.user_subdirs:
                    return False
            return True

        return False


class FHSProfile(enum.Enum):
    MINIMAL = FHSDirs()
    STANDARD = FHSDirs(
        base_dirs=MINIMAL_BASE_DIRS
        + list(map(lambda a: pathlib.Path(a), ["etc", "tmp"])),
        user_subdirs=MINIMAL_USR_DIRS,
    )


@dataclass
class FHS:
    profile: FHSProfile
    root: pathlib.Path = pathlib.Path("/")
    extended: FHSDirs | None = None

    def create(
        self,
        platform: Platform,
    ) -> None:
        base_dirs: list[pathlib.Path] = self.profile.value.base_dirs
        user_subdirs: list[pathlib.Path] = self.profile.value.user_subdirs

        if self.extended is not None:
            base_dirs += self.extended.base_dirs
            user_subdirs += self.extended.user_subdirs

        if pathlib.Path("usr") not in base_dirs and len(user_subdirs) > 0:
            raise Exception("'usr' must be in base_dirs to create user_subdirs")

        for dir in base_dirs:
            platform.comm.makedirs(path=self.root / dir, exist_ok=True)

        for usr_subdir in user_subdirs:
            platform.comm.makedirs(
                path=self.root / "usr" / usr_subdir,
                exist_ok=True,
            )


@dataclass
class Init:
    shebang: str = "#!/bin/sh"
    commands: list[str] = field(default_factory=list)

    @staticmethod
    def from_fstab(fstab: "fstab") -> Self:
        init: Init = Init()
        init.commands.append("mount -a")
        for entry in fstab.noauto_entries:
            init.commands.append(" ".join(entry.mount_point.mount_cmd()))
        return init

    def save(
        self,
        output_dir: pathlib.Path,
        platform: Platform,
        filename: str = "init",
    ) -> None:
        path: pathlib.Path = output_dir / filename
        platform.comm.write_content_to_file(
            output_filename=path,
            content=self.shebang + "\n\n" + "\n".join(self.commands) + "\n",
        )

    def save_with_fhs(
        self, fhs: FHS, platform: Platform, filename: str = "init"
    ) -> None:
        self.save(platform=platform, output_dir=fhs.root, filename=filename)


@dataclass
class InitBuilder:
    init: Init = field(default_factory=Init)

    def add_mount(
        self,
        mount_point: MountPoint,
    ) -> Self:
        self.init.commands.append(" ".join(mount_point.mount_cmd()))
        return self

    def add_cmd(self, cmd: str) -> Self:
        self.init.commands.append(cmd)
        return self

    def finalize(self) -> Init:
        return self.init


class fstabPass(enum.IntEnum):
    NO_CHECK = 0
    DURING_BOOT = 1
    AFTER_BOOT = 2


@dataclass
class fstabEntry:
    mount_point: MountPoint
    options: list[str] = field(default_factory=lambda: ["defaults"])
    dump: int = 0
    pass_num: fstabPass = fstabPass.NO_CHECK


@dataclass
class fstab:
    entries: list[fstabEntry] = field(default_factory=list)

    @property
    def noauto_entries(self) -> list[fstabEntry]:
        return [entry for entry in self.entries if "noauto" in entry.options]

    def with_init(self) -> tuple["fstab", Init]:
        return self, Init.from_fstab(fstab=self)

    def save(
        self,
        platform: Platform,
        output_path: pathlib.Path,
    ) -> None:
        lines: list[str] = [
            "# <file system> <mount point>   <type>  <options>       <dump>  <pass>"
        ]
        for entry in self.entries:
            if len(entry.options) == 0:
                raise Exception("fstab entry must have at least one option")

            options: str = (
                ",".join(entry.options) if len(entry.options) > 1 else entry.options[0]
            )

            line: str = (
                f"{entry.mount_point.what} "
                f"{entry.mount_point.where} "
                f"{entry.mount_point.fstype} "
                f"{options} "
                f"{entry.dump} "
                f"{entry.pass_num.value}"
            )
            lines.append(line)

        platform.comm.write_content_to_file(
            output_filename=output_path,
            content="\n".join(lines) + "\n",
        )


class BusyboxInit:
    def __init__(
        self,
        fhs: FHS = FHS(
            profile=FHSProfile.MINIMAL,
        ),
    ) -> None:
        if fhs.profile not in FHSProfile.STANDARD.value:
            raise Exception("BusyboxInit requires at least a STANDARD FHS profile")

        self.fhs: FHS = fhs
        self.rcS: Init | None = None
        self.fstab: fstab | None = None

    def setup_mounts(self, fstab_entries=list[fstabEntry]) -> None:
        self.fstab, self.rcS = fstab(entries=fstab_entries).with_init()
