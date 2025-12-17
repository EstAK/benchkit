# Copyright (C) 2025 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self


class PartialOrd(ABC):
    ### self < other -> bool
    @abstractmethod
    def __lt__(self, other: Self) -> bool:
        raise NotImplementedError

    ### self <= other -> true
    @abstractmethod
    def __le__(self, other: Self) -> bool:
        raise NotImplementedError

    ### self > other -> true
    @abstractmethod
    def __gt__(self, other: Self) -> bool:
        raise NotImplementedError

    ### self >= other -> true
    @abstractmethod
    def __ge__(self, other: Self) -> bool:
        raise NotImplementedError


class PartialEq(ABC):
    @abstractmethod
    def __eq__(self, other: object) -> bool:
        raise NotImplementedError

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Self):
            return NotImplemented

        return not self.__eq__(other)


class TotalOrder(PartialEq, PartialOrd):
    ### self < other -> bool
    def __lt__(self, other: Self) -> bool:
        return not self.__eq__(other) and not self.__gt__(other)

    ### self <= other -> true
    def __le__(self, other: Self) -> bool:
        return self.__eq__(other) or not self.__gt__(other)

    ### self >= other -> true
    def __ge__(self, other: Self) -> bool:
        return self.__eq__(other) or self.__gt__(other)

