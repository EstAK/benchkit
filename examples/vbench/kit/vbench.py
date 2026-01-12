# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
import os
import re
import tempfile

from enum import Enum
from dataclasses import dataclass
from typing import AnyStr, Any

from benchkit.benchmark import Benchmark
from benchkit.utils.misc import TimeMeasure
from benchkit.platforms import Platform


class Scenario(Enum):
    LIVE = "live"
    UPLOAD = "upload"
    PLATFORM = "platform"
    VOD = "vod"
    POPULAR = "popular"


@dataclass
class VideoStat:
    resolution: int
    framerate: float
    num_frames: int


class vbenchGeneric(Benchmark):
    def __init__(
        self,
        platform: Platform,
        vbench_root: pathlib.Path,
        **kwargs,
    ):
        self._vbench_root: pathlib.Path = vbench_root  # this might be useless
        self._vbench_bin: pathlib.Path = self._vbench_root / "bin"

        self.ffmpeg: pathlib.Path = self._vbench_bin / "ffmpeg"
        if not (self.ffmpeg.exists() and os.access(self.ffmpeg, os.X_OK)):
            raise Exception(
                f"Cannot find a ffmpeg executable in ffmpeg_dir: {self.ffmpeg_dir}"
            )

        self.ffprobe: pathlib.Path = self._vbench_bin / "ffprobe"
        if not (self.ffprobe.exists() and os.access(self.ffprobe, os.X_OK)):
            raise Exception(
                f"Cannot find a ffprobe executable in ffmpeg_dir: {self.ffmpeg_dir}"
            )

        self.platform: Platform = platform
        super().__init__(
            command_wrappers=[],
            command_attachments=[],
            shared_libs=[],
            pre_run_hooks=[],
            post_run_hooks=[],
            **kwargs,
        )

    def input_videos(self) -> list[pathlib.Path]:
        """
        This functions expects the class to have instantiated a video_dir member

        Returns:
            list[pathlib.Path]: list of input videos
        """
        return [
            pathlib.Path(x)
            for x in os.listdir(self._video_dir)
            if re.search("mkv$", x) or re.search("y4m$", x) or re.search("mp4$", x)
        ]

    def build_bench(
        self,
        **kwargs,
    ) -> None:
        """
        Build the benchmark, feeding to the function the build variables.
        """
        pass  # FIXME probably move the build steps here

    @staticmethod
    def check_video_dir(video_dir: pathlib.Path) -> None:
        """
        Check if the video directory is valid.
        Args:
            video_dir (pathlib.Path):
                path to the video directory
        Raises:
            Exception: if the video directory is not valid
        """
        if not (
            video_dir.is_dir()
            and os.access(video_dir, os.R_OK)
            and os.access(video_dir, os.X_OK)
        ):
            raise Exception(f"video_dir: {video_dir} is not a valid video directory")

    @property
    def bench_src_path(self) -> pathlib.Path:
        """
        Return the path to the source of the benchmark.

        Returns:
            pathlib.Path: the path to the source of the benchmark.
        """
        return self._vbench_root

    @staticmethod
    def get_build_var_names() -> list[str]:
        """
        Get the names of the build variables.

        Returns:
            List[str]: the names of the build variables.
        """
        return []

    def encode(
        self,
        input_video: pathlib.Path,
        output_video: pathlib.Path,
        settings: list[str],
        encoder: str,
    ) -> float:
        """
        Performs single pass transcoding.

        Args:
            input_video (pathlib.Path):
                path to input video
            output_video (pathlib.Path):
                path to output video
            settings (list[str]):
                list of ffmpeg settings
            encoder (str):
                encoder to use

        Returns:
            float: time to encode in nanoseconds
        """

        cmd: list[str] = (
            [
                str(self.ffmpeg),
                "-i",
                str(input_video),
                "-c:v",
                encoder,
                "-threads",
                str(1),
            ]
            + settings
            + ["-y", str(output_video)]
        )

        with TimeMeasure() as time_measure:
            _: str = self.platform.comm.shell(command=cmd, print_output=False)

        return time_measure.duration_ns

    def encode_2pass(
        self,
        input_video: pathlib.Path,
        output_file: pathlib.Path,
        settings: list[str],
        encoder: str,
    ) -> float:
        """
        Performs two pass transcoding

        Args:
            input_video (pathlib.Path):
                path to input video
            output_video (pathlib.Path):
                path to output video
            settings (list[str]):
                list of ffmpeg settings
            encoder (str):
                encoder to use

        Returns:
            float: time to encode in nanoseconds
        """
        time_to_encode1: float = self.encode(
            input_video=input_video,
            settings=["-pass", str(1), "-f", "null", "-an", "-sn"] + settings,
            output_video="/dev/null",
            encoder=encoder,
        )
        time_to_encode2: float = self.encode(
            input_video=input_video,
            settings=["-pass", str(2)] + settings,
            output_video=output_file,
            encoder=encoder,
        )

        return time_to_encode1 + time_to_encode2

    def get_psnr(
        self,
        output_video: pathlib.Path,
        input_video: pathlib.Path,
    ) -> float:
        """
        Computes PSNR between two videos using ffmpeg

        Args:
            output_video (pathlib.Path):
                path to output video
            input_video (pathlib.Path):
                path to input video
        Returns:
             PSNR between two videos using ffmpeg
        """
        cmd = (
            f"{self.ffmpeg} "
            f"-i {input_video} "
            f"-i {output_video} "
            '-lavfi "[0:v] setpts=PTS-STARTPTS[out0]; [1:v] setpts=PTS-STARTPTS[out1]; [out0][out1] psnr=log.txt" '
            "-f null - "
            "2>&1"
        )

        out: str = self.platform.comm.shell(command=cmd, shell=True, print_output=False)
        self.platform.comm.remove(path=pathlib.Path("log.txt"), recursive=False)

        m: re.Match[AnyStr] | None = re.search("average:([0-9]+\.[0-9]+)", out)
        if m is None:
            m: re.Match[AnyStr] | None = re.search("average:(if)", out)
            if m is None:
                raise Exception("no average")
            return 100.0
        else:
            return float(m.group(1))

    def get_bitrate(self, video: pathlib.Path) -> int:
        """
        Returns bitrate of a video
        Args:
            video (pathlib.Path):
                path to video
        Returns:
            bitrate (b/s) of a video
        """

        cmd: list[str] = [
            str(self.ffprobe),
            "-show_entries",
            "format=bit_rate",
            str(video),
        ]

        out: str = self.platform.comm.shell(command=cmd, print_output=False)
        m: re.Match[AnyStr] | None = re.search("bit_rate=([0-9]+)", out)
        if m is None:
            raise Exception("Cannot parse the bitrate")

        return int(m.group(1))  # report in b/s

    def get_video_stats(self, video: pathlib.Path) -> VideoStat:
        """
        Returns resolution (pixels/frame), and framerate (fps) of a video
        Args:
            video (pathlib.Path):
                path to video
        Returns:
            VideoStat: resolution, framerate, num_frames
        """

        cmd: list[str] = [
            str(self.ffprobe),
            "-show_entries",
            "stream=width,height,r_frame_rate",
            str(video),
        ]

        out: str = self.platform.comm.shell(
            command=cmd,
            environment=os.environ.copy(),
            print_output=False,
        )

        width: re.Match[AnyStr] | None = re.search("width=([0-9]+)", out)
        if width is None:
            raise Exception(
                f"Problem in fetching video width with {self.ffprobe} on {video}"
            )

        height: re.Match[AnyStr] | None = re.search("height=([0-9]+)", out)
        if height is None:
            raise Exception(
                f"Problem in fetching video height with {self.ffprobe} on {video}"
            )

        resolution: int = int(width.group(1)) * int(height.group(1))

        frame: re.Match[AnyStr] | None = re.search(
            r"r_frame_rate=(.*)$", out, re.MULTILINE
        )
        if frame is None:
            raise Exception(
                f"Problem in fetching framerate with {self.ffprobe} on {video}"
            )

        framerate: float = round(float(eval(frame.group(1))), 2)
        cmd: list[str] = [
            str(self.ffprobe),
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            str(video),
        ]
        out: str = self.platform.comm.shell(command=cmd, print_output=False)
        num_frames: re.Match[AnyStr] | None = re.search("nb_read_frames=([0-9]+)", out)

        if num_frames is None:
            raise Exception("Frames could not be parsed")

        frame_count: int = int(num_frames.group(1))

        return VideoStat(
            resolution=resolution, framerate=framerate, num_frames=frame_count
        )

    def parse_output_to_results(
        self,
        command_output: str,
        run_variables: dict[str, Any],
        **_kwargs,
    ) -> dict[str, Any]:
        return {
            k: float(v) for k, v in [x.split(":") for x in command_output.split(",")]
        }


class vbenchOther(vbenchGeneric):
    def __init__(
        self,
        platform: Platform,
        vbench_root: pathlib.Path,
        output_dir: pathlib.Path = pathlib.Path(tempfile.gettempdir()),
        **kwargs,
    ):
        self._output_dir = output_dir
        self._video_dir = vbench_root / "videos" / "crf18"
        self.check_video_dir(self._video_dir)
        super().__init__(platform=platform, vbench_root=vbench_root, **kwargs)

    @staticmethod
    def get_run_var_names() -> list[str]:
        """
        Get the names of the run variables.

        Returns:
            list[str]: the names of the run variables.
        """
        return [
            "video_name",
            "scenario",
            "encoder",
        ]

    def single_run(
        self,
        video_name: pathlib.Path,  # this is the name of the video that requires adding the correct prefix
        scenario: Scenario,
        encoder: str,
        **kwargs,
    ) -> str:
        """
        Perform a single run of the benchmark.

        Args:
            video_name (pathlib.Path):
                name of the video to transcode
            scenario (Scenario):
                scenario to use
            encoder (str):
                encoder to use
        Returns:
            str: comma separated key:value pairs with the results
        """
        video: pathlib.Path = self._video_dir / video_name
        output_video: pathlib.Path = self._output_dir / video_name
        stats: VideoStat = self.get_video_stats(video)

        target_bitrate: float = (
            3 * stats.resolution if stats.framerate > 30 else 2 * stats.resolution
        )
        bitrate: int = self.get_bitrate(video=video)
        target_bitrate: float = (
            bitrate / 2 if target_bitrate > bitrate / 2 else target_bitrate
        )
        settings: list[str] = ["-b:v", str(target_bitrate)]

        match scenario:
            case Scenario.LIVE:
                # adjust effort level depending on the video resolution
                if (stats.resolution / 1000) > 4000:
                    settings += ["-preset", "ultrafast", "-tune", "zerolatency"]
                elif (stats.resolution / 1000) > 1000:
                    settings += ["-preset", "superfast", "-tune", "zerolatency"]
                else:
                    settings += ["-preset", "veryfast", "-tune", "zerolatency"]

                elapsed: float = self.encode(
                    input_video=video,
                    settings=settings,
                    output_video=output_video,
                    encoder=encoder,
                )
            case Scenario.VOD | Scenario.PLATFORM:
                settings += ["-preset", "medium"]
                elapsed: float = self.encode_2pass(
                    input_video=video,
                    settings=settings,
                    output_file=output_video,
                    encoder=encoder,
                )
                stats.num_frames *= 2
            case Scenario.POPULAR:
                settings += ["-preset", "veryslow"]
                elapsed: float = self.encode_2pass(
                    input_video=video,
                    settings=settings,
                    output_file=output_video,
                    encoder=encoder,
                )
                stats.num_frames *= 2

            case _:
                raise NotImplementedError

        psnr: float = self.get_psnr(output_video=output_video, input_video=video)
        transcode_bitrate = self.get_bitrate(video=output_video)

        return f"elapsed:{elapsed},frames:{stats.num_frames},psnr:{psnr},bitrate:{transcode_bitrate}"


class vbenchUpload(vbenchGeneric):
    def __init__(
        self,
        platform: Platform,
        vbench_root: pathlib.Path,
        output_dir: pathlib.Path = pathlib.Path(tempfile.gettempdir()),
        **kwargs,
    ):
        self._output_dir = output_dir
        self._video_dir = vbench_root / "videos" / "crf0"
        self.check_video_dir(self._video_dir)
        super().__init__(platform=platform, vbench_root=vbench_root, **kwargs)

    @staticmethod
    def get_run_var_names() -> list[str]:
        """
        Get the names of the run variables.

        Returns:
            List[str]: the names of the run variables.
        """
        return [
            "video_name",
            "encoder",
        ]

    def single_run(
        self,
        video_name: pathlib.Path,  # this is the name of the video that requires adding the correct prefix
        encoder: str,
        **kwargs,
    ) -> str:
        """
        Perform a single run of the benchmark.

        Args:
            video_name (pathlib.Path):
                name of the video to transcode
            encoder (str):
                encoder to use
        Returns:
            str: comma separated key:value pairs with the results
        """
        input_video: pathlib.Path = self._video_dir / video_name
        output_video: pathlib.Path = self._output_dir / video_name
        stats: VideoStat = self.get_video_stats(input_video)

        elapsed: float = self.encode(
            input_video=input_video,
            settings=["-crf", "18"],
            output_video=output_video,
            encoder=encoder,
        )

        psnr: float = self.get_psnr(output_video=output_video, input_video=input_video)
        transcode_bitrate = self.get_bitrate(video=output_video)

        return f"elapsed:{elapsed},frames:{stats.num_frames},psnr:{psnr},bitrate:{transcode_bitrate}"
