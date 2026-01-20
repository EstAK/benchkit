#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from benchkit.helpers.kconfig import KConfig
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    config: KConfig = KConfig.from_file(
        path=pathlib.Path(".config"),
        platform=get_current_platform(),
    )

    if (entry := config.entries["CONFIG_FEATURE_IP_ROUTE_DIR"]) is not None:
        assert entry == '"/etc/iproute2"'
    else:
        assert False, "CONFIG_FEATURE_IP_ROUTE_DIR not found in .config"

    config.entries["CONFIG_FEATURE_IP_ROUTE_DIR"] = "hello"
    config.write_to_file(
        out=pathlib.Path(".config2"),
        platform=get_current_platform(),
    )

    other_config: KConfig = KConfig.from_file(
        path=pathlib.Path(".config2"),
        platform=get_current_platform(),
    )
    if (entry := other_config.entries["CONFIG_FEATURE_IP_ROUTE_DIR"]) is not None:
        assert entry == '"hello"'
    else:
        assert False, "CONFIG_FEATURE_IP_ROUTE_DIR not found in .config2"

    # get_current_platform().comm.remove(".config2", recursive=False)
