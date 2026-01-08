#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
import zipfile
import wget

from kit.vbench import vbenchBenchmark
from benchkit.platforms import get_current_platform
from benchkit.campaign import CampaignCartesianProduct, CampaignSuite

if __name__ == "__main__":
    vbench_zip: pathlib.Path = pathlib.Path("vbench.zip")
    if not vbench_zip.exists():
        wget.download(url="http://arcade.cs.columbia.edu/vbench/data/vbench.zip")

    if not pathlib.Path(vbench_zip.stem).exists():
        with zipfile.ZipFile(vbench_zip, "r") as zip_file:
            zip_file.extractall(path=pathlib.Path(__file__).resolve().parent)

    benchmark = vbenchBenchmark(
        platform=get_current_platform(), vbench_root=pathlib.Path("vbench")
    )
    
    campaign = CampaignCartesianProduct(name="vbench", benchmark=benchmark, nb_runs=3)
    campaigns = [campaign]

    suite = CampaignSuite(campaigns=campaigns)
    suite.print_durations()
    suite.run_suite()
