#!/usr/bin/env python3

from pathlib import Path

from benchkit.helpers.linux.fhs import MountPoint, fstab, fstabEntry, fstabPass
from benchkit.platforms import get_current_platform, Platform

if __name__ == "__main__":
    platform: Platform = get_current_platform()
    out_file: Path = Path("tmp_fstab")
    fstab_instance: fstab = fstab(
        entries=[
            fstabEntry(
                mount_point=MountPoint(
                    what=Path("/")
                    / "dev"
                    / "disk"
                    / "by-uuid"
                    / "caefd9ae-d360-44e7-99e7-e68e250f054b",
                    where=Path("/"),
                    fstype="ext4",
                )
            ),
        ]
    )

    fstab_instance.save(
        platform=platform,
        output_path=out_file,
    )

    assert platform.comm.read_file(out_file) == (
        "# <file system> <mount point>   <type>  <options>       <dump>  <pass>\n"
        "/dev/disk/by-uuid/caefd9ae-d360-44e7-99e7-e68e250f054b / ext4 defaults 0 0\n"
    )

    platform.comm.remove(path=out_file, recursive=False)
