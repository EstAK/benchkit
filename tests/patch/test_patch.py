#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from benchkit.helpers.patch import Patch
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    """
    the patch was obtained by doing :
    ```shell
    diff -u hello.c hello_new.c > file.patch
    ```
    """
    patch = Patch(
        patch_file=pathlib.Path("hello.patch"),
        cwd=pathlib.Path(__file__).parent,
        platform=get_current_platform(),
    )

    before = get_current_platform().comm.read_file("hello.c")
    patch.apply()
    patch.undo()

    assert before == get_current_platform().comm.read_file("hello.c")
