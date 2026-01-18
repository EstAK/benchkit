#!/usr/bin/env python3

import enum


# NOTE add new architectures here as needed
class Arch(enum.Enum):
    ARM = "arm"
    ARM64 = "arm64"
    MIPS = "mips"
    RISCV = "riscv"
    X86 = "x86"
    ARC = "arc"
    MICROBLAZE = "microblaze"
    XTENSA = "xtensa"


def arch_from_str(arch_str: str) -> Arch:
    match arch_str.lower():
        case "arm":
            return Arch.ARM
        case "arm64" | "aarch64":
            return Arch.ARM64
        case "mips":
            return Arch.MIPS
        case "riscv" | "riscv64":
            return Arch.RISCV
        case "x86" | "x86_64" | "amd64":
            return Arch.X86
        case "arc":
            return Arch.ARC
        case "microblaze":
            return Arch.MICROBLAZE
        case "xtensa":
            return Arch.XTENSA
        case _:
            raise ValueError(f"Unknown architecture string: {arch_str}")
