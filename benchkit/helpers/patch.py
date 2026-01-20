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
        version_prefix: pathlib.Path,
        patch_file: pathlib.Path,
    ) -> int:
        """
        Determine the patch level by examining the first '---' or '+++'
        line in the patch file.
        """
        version_prefix: str = str(version_prefix)
        patch_level = 0

        with patch_file.open("r") as pf:
            for line in pf:
                if line.startswith(("---", "+++")):
                    # strip leading '--- ' or '+++ '
                    path = line[4:].strip()
                    # count the number of leading directories until the version prefix
                    while not path.startswith(version_prefix):
                        if "/" not in path:
                            # fallback if the expected version prefix is not found
                            break
                        _, path = path.split("/", 1)
                        patch_level += 1
                    break

        return patch_level

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
