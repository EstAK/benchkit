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

    def apply(self, _reversed: bool = False) -> None:
        self.platform.comm.shell(
            command=(f"patch {'-R' if _reversed else ''} < {self.patch_file}"),
            current_dir=self.cwd,
            print_output=False,
            print_input=False,
            shell=True,
        )

    def undo(self) -> None:
        self.apply(_reversed=True)
