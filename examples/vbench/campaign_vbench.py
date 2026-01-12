#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import multiprocessing
import os
import pathlib
import tarfile
import zipfile

import wget
from kit.vbench import Scenario, vbenchOther, vbenchUpload

from benchkit.benchmark import PathEncoder
from benchkit.campaign import CampaignCartesianProduct, CampaignSuite
from benchkit.platforms import get_current_platform
from benchkit.shell.shell import shell_out
from benchkit.utils.git import clone_repo


class vbenchEncoder(PathEncoder):
    """
    Custom JSON encoder for vbench benchmarks.
    """

    def default(self, obj):
        if isinstance(obj, Scenario):
            return str(obj)
        return super().default(obj)


def build_x264(vbench_root: pathlib.Path) -> None:
    """
    Builds x264 from source and installs it into the vbench ffmpeg_build directory.

    dependencies:
        - yasm
        - nasm

    Args:
        vbench_root (pathlib.Path): The root directory of the vbench installation.
    """
    x264_bin: pathlib.Path = vbench_root / "bin" / "x264"
    x264_sources: pathlib.Path = vbench_root / "ffmpeg_sources" / "x264"

    if x264_bin.exists():
        return None

    if not x264_sources.exists():
        clone_repo(
            repo_url="https://code.videolan.org/videolan/x264.git",
            repo_src_dir=x264_sources,
            commit="90a61ec76424778c050524f682a33f115024be96",  # example commit hash
            patches=[pathlib.Path(__file__).parent / "env.patch"],
        )

    env = os.environ.copy()
    env.update({"AS": "yasm"})

    shell_out(
        [
            "./configure",
            f"--prefix={vbench_root / 'ffmpeg_build'}",
            f"--bindir={vbench_root / 'bin'}",
            "--enable-static",
        ],
        environment=env,
        current_dir=x264_sources,
    )

    shell_out(
        command=["make", f"-j{multiprocessing.cpu_count()}"],
        current_dir=x264_sources,
    )

    shell_out(
        command=["make", "install"],
        current_dir=x264_sources,
    )


def build_ffmpeg(vbench_root: pathlib.Path) -> None:
    """
    Builds FFmpeg from source and installs it into the vbench ffmpeg_build directory.
    """
    ffmpeg_tar: pathlib.Path = pathlib.Path("ffmpeg-7.0.tar.xz")
    ffmpeg_src: pathlib.Path = pathlib.Path("ffmpeg-7.0")

    if not ffmpeg_tar.exists():
        wget.download(url="http://ffmpeg.org/releases/ffmpeg-7.0.tar.xz")

    if not ffmpeg_src.exists():
        with tarfile.open(ffmpeg_tar, "r:xz") as tar_file:
            tar_file.extractall(path=pathlib.Path(__file__).resolve().parent)

    env = os.environ.copy()
    env["PKG_CONFIG_PATH"] = (
        env.get("PKG_CONFIG_PATH", "")
        + os.pathsep
        + str(vbench_root / "ffmpeg_build" / "lib" / "pkgconfig")
    )
    shell_out(
        command=[
            "./configure",
            "--disable-zlib",
            "--disable-doc",
            f"--prefix={vbench_root / 'ffmpeg_build'}",
            f"--extra-cflags=-I{vbench_root / 'ffmpeg_build' / 'include'}",
            f"--extra-ldflags=-L{vbench_root / 'ffmpeg_build' / 'lib'}",
            f"--bindir={vbench_root / 'bin'}",
            "--pkg-config-flags=--static",
            "--enable-gpl",
            "--enable-libx264",
        ],
        environment=env,
        print_input=True,
        print_output=True,
        current_dir=ffmpeg_src,
    )

    shell_out(command=["make", f"-j{multiprocessing.cpu_count()}"], current_dir=ffmpeg_src)

    shell_out(command=["make", "install"], current_dir=ffmpeg_src)


if __name__ == "__main__":
    vbench_zip: pathlib.Path = pathlib.Path("vbench.zip")
    vbench_root: pathlib.Path = pathlib.Path(__file__).resolve().parent / "vbench"

    if not vbench_zip.exists():
        wget.download(url="http://arcade.cs.columbia.edu/vbench/data/vbench.zip")

    if not vbench_root.exists():
        with zipfile.ZipFile(vbench_zip, "r") as zip_file:
            zip_file.extractall(path=pathlib.Path(__file__).resolve().parent)

    if not (vbench_root / "bin" / "x264").exists():
        build_x264(vbench_root=vbench_root)
    if not (vbench_root / "bin" / "ffmpeg").exists():
        build_ffmpeg(vbench_root=vbench_root)

    upload_benchmark = vbenchUpload(
        platform=get_current_platform(),
        vbench_root=vbench_root,
        encoder_cls=vbenchEncoder,
    )

    other_benchmark = vbenchOther(
        platform=get_current_platform(),
        vbench_root=vbench_root,
        encoder_cls=vbenchEncoder,
    )

    suite = CampaignSuite(
        campaigns=[
            CampaignCartesianProduct(
                name="vbenchUpload",
                benchmark=upload_benchmark,
                nb_runs=1,
                variables={
                    "video_name": upload_benchmark.input_videos(),
                    "encoder": ["libx264"],
                },
                constants=None,
                debug=False,
                gdb=False,
                enable_data_dir=False,
            ),
            CampaignCartesianProduct(
                name="vbenchOther",
                benchmark=other_benchmark,
                nb_runs=1,
                variables={
                    "video_name": other_benchmark.input_videos(),
                    "scenario": [
                        Scenario.VOD,
                        Scenario.LIVE,
                        Scenario.POPULAR,
                    ],
                    "encoder": ["libx264"],
                },
                constants=None,
                debug=False,
                gdb=False,
                enable_data_dir=True,
            ),
        ]
    )
    suite.print_durations()
    suite.run_suite()
