"""
This module provides classes and functions to create and manage a
Filesystem Hierarchy Standard (FHS) structure, including mount points
and an init script for mounting essential filesystems.
"""

import pathlib
import enum

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


class FHSProfile(enum.Enum):
    MINIMAL = FHSDirs()
    STANDARD = FHSDirs(
        base_dirs=MINIMAL_BASE_DIRS
        + list(map(lambda a: pathlib.Path(a), ["mnt", "tmp"])),
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
class InitBuilder:
    platform: Platform
    source_path: pathlib.Path
    shebang: str = "#!/bin/sh"
    commands: list[str] = field(default_factory=list)

    def add_mount(
        self,
        mount_point: MountPoint,
    ) -> None:
        self.commands.append(" ".join(mount_point.mount_cmd()))

    def save(self) -> None:
        path: pathlib.Path = self.source_path / "init"
        self.platform.comm.write_content_to_file(
            output_filename=path,
            content=self.shebang + "\n\n" + "\n".join(self.commands) + "\n",
        )


@dataclass
class Init:
    source_path: pathlib.Path
    platform: Platform
    builder: InitBuilder | None = None

    @staticmethod
    def from_fhs(fhs: FHS, platform: Platform) -> "Init":
        return Init(
            source_path=fhs.root,
            platform=platform,
        )

    def __enter__(self) -> InitBuilder:
        self._builder = InitBuilder(
            source_path=self.source_path,
            platform=self.platform,
        )
        return self._builder

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None:
            return False  # propagate exception

        assert self._builder is not None
        self._builder.save()


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
