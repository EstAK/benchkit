# Copyright (C) 2026 Vrije Universiteit Brussel, Ltd. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib

from typing import Self, Iterable
from dataclasses import dataclass, field


class __Token:
    def __eq__(self, other) -> bool:
        if not isinstance(other, str):
            return NotImplemented
        return other == self._inner

    def __str__(self) -> str:
        return self._inner


class _Quote(__Token):
    _inner: str = '"'


class _Hashtag(__Token):
    _inner: str = "#"


class _Equal(__Token):
    _inner: str = "="


class _EOL(__Token):
    _inner: str = "\n"


@dataclass
class _Ident:
    content: str

    def try_downcast(self) -> int | bool | Self:
        """
        Try to downcast the identifier to int or bool if possible.

        return:
            The downcasted value or self if not possible.
        """
        match self.content:
            case "y":
                return True
            case "n":
                return False
            case ch if ch.isdigit():
                return int(ch)
            case _:
                return self

    def __str__(self) -> str:
        return self.content


KConfigRHS = int | bool | str
_KConfigSyntax = _Equal | _Quote | _Hashtag | _EOL | _Ident | int | bool
_transitions: dict[None | _KConfigSyntax, None | _KConfigSyntax] = {
    None: [_Ident, _Hashtag],
    _Ident: [_Equal, _EOL, _Quote],
    _Hashtag: [_Ident],
    _Equal: [_Ident, _Quote, int, bool],
    _Quote: [_Ident, _Quote],
    bool: [_EOL],
    int: [_EOL],
    _EOL: [],
}


@dataclass
class KConfigEntry:
    key: str
    value: KConfigRHS


@dataclass(slots=True)
class _KConfigEntryTokenStream:
    _tokens: list[_KConfigSyntax] = field(default_factory=list)
    _pos: int = 0

    @property
    def _prev(self) -> _KConfigSyntax | None:
        if self._pos - 1 >= 0:
            return self._tokens[self._pos - 1]
        return None

    def __str__(self) -> str:
        return " -> ".join(str(token) for token in self._tokens)

    def add(self, token: _KConfigSyntax) -> None:
        """
        Add a token to the stream after validation. Raises an exception if the token is invalid.
        """
        if self._pos > 0 and type(token) not in _transitions[type(self._prev)]:
            raise Exception(f"Invalid token sequence : {self._tokens} + {type(token)}")
        self._pos += 1
        self._tokens.append(token)  # add the token if no exception was raised

    def entry(self) -> KConfigEntry | None:
        if isinstance(self._tokens[0], _Hashtag):
            return None

        # when the entry is of the form KEY=VALUE where VALUE is a single token
        if len(self._tokens) == 4:
            lhs, _eq, rhs, _eol = self._tokens
            return KConfigEntry(
                key=lhs.content,
                value=rhs.try_downcast(),
            )

        # if the value is compounded: use a string
        return KConfigEntry(
            key=self._tokens[0].content,
            value="".join(
                [
                    str(tok.try_downcast()) if isinstance(tok, _Ident) else str(tok)
                    for tok in self._tokens[1:]
                    if not isinstance(tok, (_Equal, _EOL))
                ]
            ),
        )


def parse_kconfig_entry(raw_entry_str: Iterable[str]) -> KConfigEntry | None:
    buffer: str = ""
    token_stream: _KConfigEntryTokenStream = _KConfigEntryTokenStream()
    for c in raw_entry_str:
        match c:
            case ch if ch == _Hashtag():
                token_stream.add(_Hashtag())
                buffer = ""  # reset the buffer to avoid adding EOL by mistake
                break

            case ch if ch == _Equal():
                # no need to downcast as lhs cannot be int or bool
                token_stream.add(_Ident(buffer))
                token_stream.add(_Equal())
                buffer = ""

            case ch if ch == _Quote():
                # don't add an empty ident
                if len(buffer) > 0:
                    token_stream.add(_Ident(buffer))
                    buffer = ""

                token_stream.add(_Quote())

            case ch if ch.isalnum() or ch in "_-./(),":
                buffer += ch

            case ch if ch == _EOL():
                token_stream.add(_Ident(buffer))
                token_stream.add(_EOL())
                buffer = ""

            case " ":  # ignore whitespace
                continue

            case _:
                raise Exception(f"unexpected character: {c} in entry: {raw_entry_str}")

    if len(buffer) > 0 and not isinstance(token_stream._tokens[-1], _Hashtag):
        token_stream.add(_Ident(buffer))
        token_stream.add(_EOL())

    return token_stream.entry()


@dataclass
class KConfig:
    entries: dict[str:KConfigRHS]

    @classmethod
    def from_file(cls, path: pathlib.Path) -> Self:
        entries: dict[str:KConfigRHS] = dict()
        with open(path, "r") as f:
            for line in f:
                if (entry := parse_kconfig_entry(line)) is not None:
                    entries[entry.key] = entry.value

        return cls(entries=entries)

    def write_to_file(self, out: pathlib.Path | None = None) -> None:
        with open(out if out is not None else self._dot_config_path, "w") as f:
            for key, value in self.entries.items():
                if isinstance(value, bool):
                    f.write(f"{key}={'y' if value else 'n'}\n")
                else:
                    f.write(f'{key}="{value}"\n')
