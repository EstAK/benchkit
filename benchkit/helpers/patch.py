# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
from dataclasses import dataclass

from benchkit.platforms import Platform


@dataclass
class Patch:
    patch_file: pathlib.Path
    cwd: pathlib.Path
    platform: Platform
    pnum: int = 0

    @staticmethod
    def detect_patch_level(
        prefix: str,
        patch_file: pathlib.Path,
        platform: Platform,
    ) -> int:
        """
        Detect the patch level of a patch file.
        """
        pf: list[str] = platform.comm.read_file(patch_file).splitlines()
        try:
            minus: str = next((line for line in pf if line.startswith("---")), "")
            pnum: int = 0
            for tok in minus.split("/"):
                if tok.startswith(prefix):
                    return pnum
                pnum += 1
        except StopIteration:
            return 0

    def apply(self, _reversed: bool = False) -> None:
        self.platform.comm.shell(
            command=(
                f"patch -p{self.pnum} {'-R' if _reversed else ''} < {self.patch_file}"
            ),
            current_dir=self.cwd,
            print_output=False,
            print_input=False,
            shell=True,
        )

    def undo(self) -> None:
        self.apply(_reversed=True)

    def is_applied(self) -> bool:
        """
        Check if the patch is already applied.
        """
        msg: str = "Reversed (or previously applied) patch detected!"
        out: str = self.platform.comm.shell(
            command=f"patch --dry-run -t -s -p{self.pnum} < {self.patch_file} 2>&1",
            current_dir=self.cwd,
            print_output=False,
            print_input=False,
            shell=True,
        )

        return msg in out
