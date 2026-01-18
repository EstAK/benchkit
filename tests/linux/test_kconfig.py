#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from benchkit.helpers.kconfig import KConfig, KConfigEntry
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    config: KConfig = KConfig(kconfig_path=pathlib.Path(".config"))
    if (entry := config.get_entry("CONFIG_FEATURE_IP_ROUTE_DIR")) is not None:
        assert entry == '"/etc/iproute2"'
    else:
        assert False, "CONFIG_FEATURE_IP_ROUTE_DIR not found in .config"

    config.set_entry(KConfigEntry(key="CONFIG_FEATURE_IP_ROUTE_DIR", value="hello"))
    config.update_file(out=pathlib.Path(".config2"))

    other_config: KConfig = KConfig(kconfig_path=pathlib.Path(".config2"))
    if (entry := other_config.get_entry("CONFIG_FEATURE_IP_ROUTE_DIR")) is not None:
        assert entry == '"hello"'
    else:
        assert False, "CONFIG_FEATURE_IP_ROUTE_DIR not found in .config2"

    get_current_platform().comm.remove(".config2", recursive=False)
