#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.helpers.version import SemanticVersion, LinuxVersion

if __name__ == "__main__":

    rev = LinuxVersion.from_str("6.18-rc5")
    assert rev.major == 6
    assert rev.minor == 18
    assert rev.patch == 0
    assert rev.revision == "rc5"

    rev = LinuxVersion.from_str("6.18.3-alpha")

    assert rev.major == 6
    assert rev.minor == 18
    assert rev.patch == 3
    assert rev.revision == "alpha"

    rev = SemanticVersion.from_str("6.18")
    assert rev.major == 6
    assert rev.minor == 18
    assert rev.patch == 0

    rev = SemanticVersion.from_str("6.18.3")
    assert rev.major == 6
    assert rev.minor == 18
    assert rev.patch == 3
