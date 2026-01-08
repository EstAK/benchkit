# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
import tempfile
import os
import re

from enum import Enum
from dataclasses import dataclass
from typing import AnyStr

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


class vbenchConfig:
    def __init__(
        self,
        # Transcoding scenario
        scenario: Scenario,
        # Path to ffmpeg installation folder
        ffmpeg_dir: pathlib.Path,
        # Where to save transcoded videos
        output_dir: pathlib.Path = pathlib.Path(tempfile.gettempdir()),
        # FFmpeg encoder to use
        encoder: str = "libx264",  # FIXME move to an enum when set is known
    ) -> None:
        self.scenario: pathlib.Path = scenario
        self.ffmpeg_dir: pathlib.Path = ffmpeg_dir
        self.output_dir: pathlib.Path = output_dir
        self.encoder: pathlib.Path = encoder

        self.ffmpeg: pathlib.Path = self.ffmpeg_dir / "ffmpeg"
        if not (self.ffmpeg.exists() and os.access(self.ffmpeg, os.X_OK)):
            raise Exception(
                f"Cannot find a ffmpeg executable in ffmpeg_dir: {self.ffmpeg_dir}"
            )

        self.ffprobe: pathlib.Path = self.ffmpeg_dir / "ffprobe"
        if not (self.ffprobe.exists() and os.access(self.ffprobe, os.X_OK)):
            raise Exception(
                f"Cannot find a ffprobe executable in ffmpeg_dir: {self.ffmpeg_dir}"
            )

        if not (self.output_dir.is_dir() and os.access(self.output_dir, os.W_OK)):
            raise Exception(f"Output directory {self.output_dir} is non writable")


class vbenchBenchmark(Benchmark):
    def __init__(
        self,
        platform: Platform,
        vbench_root: pathlib.Path,
    ):
        super().__init__(platform=platform)
        self._vbench_root = vbench_root

    @staticmethod
    def get_run_var_names() -> list[str]:
        """
        Get the names of the run variables.

        Returns:
            List[str]: the names of the run variables.
        """
        return [
            "config",
            "input_video",
        ]

    def single_run(self, config: vbenchConfig, input_video: pathlib.Path) -> str:
        video_dir: pathlib.Path = (
            self._vbench_root / "videos" / "crf0"
            if config.scenario == Scenario.UPLOAD
            else self._vbench_root / "videos" / "crf18"
        )

        if not (
            video_dir.is_dir()
            and os.access(video_dir, os.R_OK)
            and os.access(video_dir, os.X_OK)
        ):
            raise Exception(f"video_dir: {video_dir} is not a valid video directory")

        if video_dir.absolute() == config.output_dir.absolute():
            raise Exception("Output and video input directory can not be the same")

        inputs = {
            pathlib.Path(x)
            for x in os.listdir(video_dir)
            if re.search("mkv$", x) or re.search("y4m$", x) or re.search("mp4$", x)
        }

        

        total_frames: int = 0
        total_elapsed: float = 0.0
        total_frames: int = 0
        res: list[str] = list()
        for video_name in inputs:
            video: pathlib.Path = video_dir / video_name
            output_video: pathlib.Path = config.output_dir / video_name
            stats: VideoStat = self.get_video_stats(video)

            if config.scenario == Scenario.UPLOAD:
                settings: list[str] = ["-crf", "18"]
                # self.encode() # TODO compute elapsed
            else:
                total_frames += stats.num_frames
                target_bitrate: int = (
                    3 * stats.resolution
                    if stats.framerate > 30
                    else 2 * stats.resolution
                )
                bitrate: int = self.get_bitrate(video=video)
                target_bitrate: float = (
                    bitrate / 2 if target_bitrate > bitrate / 2 else target_bitrate
                )
                settings: list[str] = ["-b:v", str(target_bitrate)]

            match config.scenario:
                case Scenario.LIVE:
                    # adjust effort level depending on the video resolution
                    if (stats.resolution / 1000) > 4000:
                        settings += ["-preset", "ultrafast", "-tune", "zerolatency"]
                    elif (stats.resolution / 1000) > 1000:
                        settings += ["-preset", "superfast", "-tune", "zerolatency"]
                    else:
                        settings += ["-preset", "veryfast", "-tune", "zerolatency"]

                    elapsed: float = self.encode(
                        self.ffmpeg, video, settings, output_video, config.encoder
                    )
                case Scenario.VOD | Scenario.PLATFORM:
                    settings += ["-preset", "medium"]
                    elapsed: float = self.encode_2pass(
                        video=video,
                        settings=settings,
                        output_file=output_video,
                        encoder=config.encoder,
                    )
                    stats.num_frames *= 2
                case Scenario.POPULAR:
                    settings += ["-preset", "veryslow"]
                    elapsed: float = self.encode_2pass(
                        video=video,
                        settings=settings,
                        output_file=output_video,
                        encoder=config.encoder,
                    )
                    stats.num_frames *= 2

                case _:
                    raise NotImplementedError

            psnr: float = self.get_psnr(output_video=output_video, input_video=video)
            transcode_bitrate = self.get_bitrate(video=output_video)
            res += f"{video_name},{elapsed}, {psnr}, {transcode_bitrate}"

            # print("{},{},{},{}".format(v_name, elapsed, psnr, transcode_bitrate))
            total_elapsed += elapsed
            total_frames += stats.num_frames

        res += ""
        res += f"total_elapsed:{total_elapsed}"
        res += f"total_frames:{total_frames}"
        res += f"avg_fps:{total_frames / total_elapsed}"

        return res

    def encode(
        self,
        video: pathlib.Path,
        settings: list[str],
        output: pathlib.Path,
        encoder: str,
    ) -> float:
        """perform the transcode operation using ffmpeg"""

        cmd: list[str] = (
            [self.ffmpeg, "-i", video, "-c:v", encoder, "-threads", str(1)]
            + settings
            + ["-y", output]
        )

        with TimeMeasure() as time_measure:
            _: str = self.platform.comm.shell(command=cmd, shell=True)

        return time_measure.duration_ns

    def encode_2pass(self, video, settings, output_file, encoder) -> float:
        """perform two pass transcoding"""
        time_to_encode1: float = self.encode(
            video,
            ["-pass", str(1), "-f", "null", "-an", "-sn"] + settings,
            "/dev/null",
            encoder,
        )
        time_to_encode2: float = self.encode(
            video, ["-pass", str(2)] + settings, output_file, encoder
        )

        return time_to_encode1 + time_to_encode2

    def get_psnr(self, output_video: pathlib.Path, input_video: pathlib.Path) -> float:
        cmd: str = (
            f"{self.ffmpeg} "
            f"-i {input_video} -i {output_video} "
            '-lavfi "[0:v] setpts=PTS-STARTPTS[out0]; '
            "[1:v] setpts=PTS-STARTPTS[out1]; "
            '[out0][out1] psnr=log.txt" '
            "-f null - 2>&1"
        )

        out: str = self.platform.comm.shell(command=cmd, shell=True)
        m: re.Match[AnyStr] | None = re.search("average:([0-9]+\.[0-9]+)", out)

        # cleanup
        self.platform.comm.shell(command="rm log.txt")

        if m is None:
            m: re.Match[AnyStr] | None = re.search("average:(inf)", err.decode("utf-8"))
            if m is None:
                raise Exception("no average")
            return 100.0
        else:
            return float(m.group(1))

    def get_bitrate(self, video: pathlib.Path) -> int:
        """Returns bitrate (bit/s)"""
        cmd: list[str] = [self.ffprobe, "-i", video, "2>&1"]
        out: str = self.platform.comm.shell(command=cmd, shell=True)

        m: re.Match[AnyStr] | None = re.search("bitrate: ([0-9]+) kb/s", out)
        if m is None:
            raise Exception("Cannot parse the bitrate")

        return int(m.group(1)) * 1000  # report in b/s

    def get_video_stats(self, video: pathlib.Path) -> VideoStat:
        """Returns resolution (pixels/frame), and framerate (fps) of a video"""

        # run ffprobe
        cmd: list[str] = [
            self.ffprobe,
            "-show_entries",
            "stream=width,height",
            video,
            "2>&1",
        ]
        out: str = self.platform.comm.shell(command=cmd, shell=True)
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

        frame: re.Match[AnyStr] | None = re.search("([0-9\.]+) fps", out)
        if frame is None:
            raise Exception(
                f"Problem in fetching framerate with {self.ffprobe} on {video}"
            )

        framerate: float = float(frame.group(1))
        cmd: list[str] = [
            self.ffprobe,
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            video,
            "2>&1",
        ]
        out: str = self.platform.comm.shell(command=cmd, shell=True)
        num_frames: re.Match[AnyStr] | None = re.search("nb_read_frames=([0-9]+)", out)

        if num_frames is None:
            raise Exception("Frames could not be parsed")

        frame_count: int = int(num_frames.group(1))

        return VideoStat(
            resolution=resolution, framerate=framerate, num_frames=frame_count
        )
