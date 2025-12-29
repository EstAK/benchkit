# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field
from typing import Set

@dataclass
class CPUTopology:
    """
    Class representing the topology of a CPU
    """
    nb_cores: int
    nb_threads_per_core: int
    nb_sockets: int = 1
    isolated_cores: Set[int] = field(default_factory=set)
