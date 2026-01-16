#!/usr/bin/env python3
# Copyright (C) 2026 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from enum import Enum
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PeriodicTask:
    runtime: int  # nanoseconds
    period: int  # nanoseconds
    deadline: int  # nanoseconds

    def __post_init__(self):
        if not (0 < self.runtime <= self.deadline <= self.period):
            raise ValueError("Must satisfy: 0 < runtime ≤ deadline ≤ period")

    def to_cmd(self) -> list[str]:
        return [
            "--sched-runtime",
            str(self.runtime),
            "--sched-period",
            str(self.period),
            "--sched-deadline",
            str(self.deadline),
        ]


class Policy(Enum):
    OTHER = "--other"
    FIFO = "--fifo"
    RR = "--rr"
    BATCH = "--batch"
    IDLE = "--idle"
    DEADLINE = "--deadline"

    @property
    def is_realtime(self) -> bool:
        return self in {Policy.RR, Policy.BATCH, Policy.DEADLINE}


CHRT_CMD: str = "chrt"


def chrt_info(
    pid: int,
    all_tasks: bool = False,
) -> list[str]:
    cmd = [CHRT_CMD]
    if all_tasks:
        cmd.append("--all-tasks")
    cmd.extend(["-p", str(pid)])
    return cmd


def chrt_run_command(
    target: int | pathlib.Path,
    all_tasks: bool,
    policy: Policy,
    priority: int = 0,
    reset_on_fork: bool = False,
    periodic_task: PeriodicTask | None = None,
) -> list[str]:
    """
    Build a chrt command.

    target:
        PID (int) to modify, or program path (Path) to execute
    all_tasks:
        Apply to all threads of a PID (PID mode only)
    policy:
        Scheduling policy
    priority:
        Static priority (FIFO/RR only)
    reset_on_fork:
        Reset scheduling attributes on fork
    periodic_task:
        Required for SCHED_DEADLINE
    """
    cmd: list[str] = [CHRT_CMD]
    is_pid: bool = isinstance(target, int)

    if all_tasks:
        if not is_pid:
            raise ValueError("only available for a given pid")
        cmd.append("--all-tasks")

    if reset_on_fork:
        cmd.append("--reset-on-fork")
    cmd.append(policy.value)

    if policy == Policy.DEADLINE:
        if periodic_task is None:
            raise ValueError("SCHED_DEADLINE requires PeriodicTask")
        if priority != 0:
            raise ValueError("SCHED_DEADLINE does not use priority")

        cmd.extend(periodic_task.to_cmd())
    else:
        if periodic_task is not None:
            raise ValueError("PeriodicTask is only valid with SCHED_DEADLINE")

        match policy:
            case policy.BATCH | policy.IDLE | policy.OTHER:
                if priority != 0:
                    raise ValueError(f"{policy.name} requires priority = 0")
            case policy.FIFO | policy.RR:
                if not (1 <= priority <= 99):
                    raise ValueError("FIFO/RR priority must be in range [1, 99]")
            case _:
                raise Exception("assert never placeholder")

    if is_pid:
        cmd.extend(["-p", str(priority), str(target)])
    else:
        cmd.extend([str(priority), str(target)])

    return cmd
