#!/usr/bin/env python3


class Network:
    """
    Network interface.
    """

    @property
    def ip_address(self) -> str: ...

    def remote_host(self) -> str | None: ...
