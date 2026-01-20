# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from typing import Self
from enum import Enum


# NOTE add new architectures here as needed
class Arch(Enum):
    ARM = "arm"
    ARM64 = "arm64"
    MIPS = "mips"
    RISCV = "riscv"
    X86_64 = "x86_64"
    X86 = "x86"
    ARC = "arc"
    MICROBLAZE = "microblaze"
    XTENSA = "xtensa"

    @classmethod
    def from_str(cls, value: str) -> Self:
        v: str = value.lower().strip()

        if v in ("arm64", "aarch64"):
            return cls.ARM64
        elif v in ("riscv", "riscv64"):
            return cls.RISCV
        elif v in ("x86_64", "amd64"):
            return cls.X86_64
        elif v in ("x86", "i386"):
            return cls.X86

        try:
            return cls(v)
        except ValueError:
            raise ValueError(f"Unknown architecture string: {value}")
