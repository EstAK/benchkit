#!/usr/bin/env python3

import time

from benchkit.commandwrappers.stressng import StressNgContext
from benchkit.platforms import get_current_platform

if __name__ == "__main__":
    before: float = time.monotonic()
    with StressNgContext(
        args={"--cpu": "2"},
        cmds=[],
        platform=get_current_platform(),
    ):
        time.sleep(10)
    duration: float = time.monotonic() - before
    assert round(duration, 0) == 10
