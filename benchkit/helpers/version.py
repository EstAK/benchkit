# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from typing import Self

import functools


@dataclass
@functools.total_ordering
class SemanticVersion:
    """
    An abstraction to version semver compliants entities
    """
    major: int = 0
    minor: int = 0
    patch: int = 0
    revision: str = ""  # not used for comparison

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Self):
            return NotImplemented

        return (
            self.major,
            self.minor,
            self.patch,
        ) == (
            other.major,
            other.minor,
            other.patch,
        )

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Self):
            return NotImplemented

        return (
            self.major,
            self.minor,
            self.patch,
        ) > (
            other.major,
            other.minor,
            other.patch,
        )

    def __str__(self):
        version: str = f"{self.major}.{self.minor}.{self.patch}"
        if self.revision != "":
            version += f"-{self.revision}"
        return version

    @classmethod
    def from_str(cls, version_str: str) -> Self:
        parts: list[str] = version_str.split(".")
        if not 2 <= len(parts) <= 3:
            raise ValueError(f"Invalid version: {version_str}")

        return cls(*map(lambda a: int(a), parts))


class LinuxVersion(SemanticVersion):
    """
    An abstraction for a versioning the Linux kernel as it does not use standard semver

    Example:

    To version Linux,

        Linux 6.18.5 -> patch
            |  +----> minor
            +-------> major

        Linux 6.19-rc5 -> revision
              |  +------> minor
              +---------> major

    """

    revision: str = ""  # not used for comparison

    def __str__(self):
        version: str = f"{self.major}.{self.minor}"
        if self.patch > 0:
            version += f".{self.patch}"
        if self.revision != "":
            version += f"-{self.revision}"
        return version

    @classmethod
    def from_str(cls, version_str: str) -> Self:
        version, *rev = version_str.split("-", 1)
        revision: str = rev[0] if rev else ""

        parts: list[str] = version.split(".")
        if not 2 <= len(parts) <= 3:
            raise ValueError(f"Invalid version: {version_str}")

        versions: list[int] = list(map(int, parts))
        versions.extend((3 - len(parts)) * [0])  # fill to semver
        return cls(*versions, revision)
