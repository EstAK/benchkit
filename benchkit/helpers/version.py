# Copyright (C) 2025 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Self
from . import ordering


class SemanticVersion(ordering.TotalOrder):

    def __init__(
        self,
        major: int = 0,
        minor: int = 0,
        patch: int = 0,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Self):
            return NotImplemented

        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __gt__(self, other: Self) -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)
