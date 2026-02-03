#!/usr/bin/env python3

import pathlib
import shutil

from benchkit.helpers.linux.fhs import (
    FHS,
    FHSProfile,
    Init,
    MountPoint,
    PROC,
    SYS,
    DEV,
    InitBuilder,
)

from benchkit.platforms import Platform, get_current_platform

if __name__ == "__main__":
    test_root: pathlib.Path = pathlib.Path("test_root")
    fhs = FHS(
        profile=FHSProfile.STANDARD,
        root=test_root,
    )

    platform: Platform = get_current_platform()
    fhs.create(platform)

    init = (
        InitBuilder()
        .add_mount(mount_point=PROC)
        .add_mount(mount_point=SYS)
        .add_mount(mount_point=DEV)
    ).finalize()
    init.save_with_fhs(fhs=fhs, platform=platform)

    assert (test_root / "proc").is_dir()
    assert (test_root / "sys").is_dir()
    assert (test_root / "dev").is_dir()
    assert (test_root / "bin").is_dir()
    assert (test_root / "sbin").is_dir()
    assert (test_root / "lib").is_dir()

    shutil.rmtree(test_root)

    print("FHS test completed successfully.")
