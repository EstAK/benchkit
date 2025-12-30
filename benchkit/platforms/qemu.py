# Copyright (C) 2025 Vrije Universiteit Brussel. All rights reserved.
# SPDX-License-Identifier: MIT

from benchkit.platforms.generic import Platform
from benchkit.communication.generic import CommunicationLayer, StatusAware
from benchkit.communication.qemu import QEMUCommLayer, QEMUPty
from benchkit.helpers.qemu import QEMUConfig

from benchkit.utils import lscpu

from typing import List, Generic, TypeVar, get_args


class QEMUPlatformException(Exception):
    pass


class _QEMUCommonPlatform(Platform):
    """
    Represent a generic QEMU platform on top of which a user builds a concrete platform
    """

    def __init__(
        self,
        comm_layer: CommunicationLayer | None,
        qemu_config: QEMUConfig,
    ) -> None:
        self._comm_layer: CommunicationLayer | None = comm_layer
        self._qemu_config: QEMUConfig = qemu_config

    @property
    def comm(self) -> CommunicationLayer:
        """
        Get the communication layer of the host associated with the current platform.

        Returns:
            CommunicationLayer:
                the communication layer of the host associated with the current platform.
        """
        return NotImplemented

    def _get_lscpu(self) -> lscpu.LsCpu:
        raise NotImplemented  # TODO QEMU might not have lscpu, check this out

    # FIXME the platform self variables that do not exist in self
    def nb_cpus_per_cache_partition(self) -> int:
        raise NotImplemented

    def nb_cache_partition_per_numa_node(self) -> int:
        raise NotImplemented

    def nb_cpus_per_numa_node(self) -> int:
        raise NotImplemented

    def nb_cpus_per_package(self) -> int:
        raise NotImplemented

    def nb_hyperthreads_per_core(self) -> int:
        """
        Get the number of hyperthreads (or CPUs) per core.

        Returns:
            int: the number of hyperthreads (or CPUs) per core.
        """
        return self._qemu_config._cpu_topology.nb_threads_per_core

    @property
    def architecture(self) -> str:
        """
        Get the architecture of the platform.

        Returns:
            str: the architecture of the platform.
        """
        return self._qemu_config._target_arch.__str__()

    def nb_cpus(self) -> int:
        """
        Get the total number of CPUs of the platform.
        It represents the number of "hyperthreads" in the system, i.e. the amount of CPUs visible
        by the operating system.

        Returns:
            int: the total number of CPUs of the platform.
        """
        return self._qemu_config._cpu_topology.nb_cores

    def nb_active_cpus(self) -> int:
        """
        Get the number of CPUs of the platform that are active (not isolated).

        Returns:
            int: the number of CPUs of the platform that are active (not isolated).
        """
        return self._qemu_config._guest_logical_cores - len(
            self._qemu_config._cpu_topology.isolated_cores
        )

    def nb_isolated_cpus(self) -> int:
        """
        Get the number of CPUs of the platform that are isolated (not active).

        Returns:
            int: the number of CPUs of the platform that are isolated (not active).
        """
        # does *only* count the isolated CPUs in the count
        return len(self._qemu_config._cpu_topology.isolated_cores)

    def nb_hyperthreaded_cores(self) -> int:
        """
        Get the number of cores (possibly hyperthreaded) of the platform.
        For example, on x86_64, there are 2 CPUs per core (or 2 hyperthread per core).
        On Armv8, there is no SMT (no hyperthreading), so there is 1 CPU per core.
        On Armv8, we have nb_hyperthreaded_cores() == nb_cpus().

        Returns:
            int: the number of cores of the platform, possibly hyperthreaded.
        """
        return (
            self._qemu_config._cpu_topology.nb_cores
            // self._qemu_config._cpu_topology.nb_threads_per_core
        )

    def nb_cache_partitions(self) -> int:
        """
        Get the total number of cache partitions (or cache groups) of the platform.

        Returns:
            int: _description_
        """
        # NOTE how valid is it for qemu ?
        # conservative assumption in the absence of the precise information:
        return self.nb_hyperthreaded_cores()

    def nb_numa_nodes(self) -> int:
        """
        Get the total number of NUMA nodes of the platform.

        Returns:
            int: the total number of NUMA nodes of the platform.
        """
        return NotImplemented

    def nb_packages(self) -> int:
        """
        Get the total number of packages (or sockets) of the platform.

        Returns:
            int: the total number of packages (or sockets) of the platform.
        """
        return self._qemu_config._cpu_topology.nb_sockets

    def cache_line_size(self) -> int | None:
        """
        Get the size (in bytes) of one cache line on the platform.
        It returns None if this information is not known.

        Returns:
            int | None: the size (in bytes) of one cache line on the platform.
        """
        return NotImplemented  # TODO https://www.qemu.org/docs/master/system/qemu-manpage.html

    def cpu_order(
        self,
        provided_order: str | List[int] = "asc",  # TODO use the CpuOrder type
    ) -> List[int]:
        """
        Provide the list of CPU identifiers in the order matching the given specified CPU order.
        For example, if the provided order is "asc" on a platform with 4 cores, the result will be
        [0, 1, 2, 3]. If the provided order is "desc", the result will be [3, 2, 1, 0], etc.

        Args:
            provided_order (str | List[int], optional):
                Specification of the CPU order. Defaults to "asc".

        Raises:
            NotImplementedError: if the specified order is not recognized.

        Returns:
            List[int]: list of CPU identifiers of the platform matching the specified CPU order.
        """
        if not isinstance(provided_order, str):
            if all(isinstance(cid, int) for cid in provided_order):
                # if the provided order is a list of integer core id, returns it
                # as the selected cpu_order.
                return provided_order

        nb_cpus = self.nb_cpus()

        match provided_order:
            case "even":
                return NotImplemented
            case "desc":
                result_ordering = list(range(nb_cpus - 1, -1, -1))
            case "asc":
                result_ordering = list(range(1, nb_cpus, 1)) + [0]
            case _:
                raise NotImplementedError(
                    f"Unknown core ordering technique: {provided_order}"
                )

        return result_ordering

    def master_thread_core_id(self, cpu_order_list: List[int]) -> int:
        """
        Given a list of CPU identifiers that will be a thread-to-core assignment, return on what
        core should the main thread (first thread to start the process) be executed.
        Ensuring the first thread runs on that core usually yield better performance, as the memory
        allocation policy will be based on where is the main thread currently executing (as the
        main thread is usually in charge of allocating memory for the other threads).
        We selected the following policy: the allocator thread should be the first one of the NUMA
        node of thread with tid 1 (the second thread to be created).

        Args:
            cpu_order_list (List[int]):
                given order of CPU identifiers for a thread-to-core assignment.

        Returns:
            int: where the main thread should be running.
        """
        return NotImplemented

    def cpu_order_even(self) -> List[int]:
        """
        Provide the "even" distribution of threads on the current platform.
        This means that two "adjacent" threads (thread created one after the other) will be
        scheduled as far from each other as possible.
        This CPU order distribution is especially useful when one desire to measure the
        cross-package and cross-NUMA nodes latencies.

        Returns:
            List[int]:
                list of CPU identifiers corresponding to the even distribution on the current
                platform.
        """

        return NotImplemented

    def kernel_version(self) -> str:
        """
        Identifier of the kernel ("uname -r") running currently on the platform.

        Returns:
            str: identifier of the kernel running currently on the platform.
        """
        return NotImplemented

    def current_user(self) -> str:
        """
        Get the name of the current user logged in the platform.

        Returns:
            str: the name of the current user logged in the platform.
        """
        return NotImplemented


# TODO ad hoc new qemu approved communication layers
T = TypeVar("T", bound=[CommunicationLayer, StatusAware])


class QEMUMachine(_QEMUCommonPlatform, Generic[T]):
    def __init__(
        self,
        comm_layer: T | None,
        qemu_config: QEMUConfig | None,
    ) -> None:
        super().__init__(comm_layer, qemu_config)

    @property
    def comm(self) -> T:
        """
        Get the communication layer of the host associated with the current platform.

        Returns:
            Generic(bound=CommunicationLayer):
                the communication layer of the host associated with the current platform.
        """
        # NOTE should the platform start the communication ?
        return self._comm_layer


class QEMUIntrospection(_QEMUCommonPlatform, Generic[T]):
    def __init__(
        self,
        comm_layer: QEMUCommLayer,
        qemu_config: QEMUConfig,
    ) -> None:
        # we can use other types of communication layer in the future depending on our needs
        self._machine: QEMUMachine[T] | None = None
        super().__init__(comm_layer, qemu_config)

    def machine(self, comm: T) -> QEMUMachine[T]:
        if self._machine is None:
            self._machine = QEMUMachine(qemu_config=self._qemu_config, comm_layer=comm)

        return self._machine

    @property
    def comm(self) -> CommunicationLayer:
        """
        Get the communication layer of the host associated with the current platform.

        Returns:
            CommunicationLayer:
                the communication layer of the host associated with the current platform.
        """
        # NOTE should the platform start the communication ?
        if not self._comm_layer.is_open():
            self._comm_layer.start_comm()

        return self._comm_layer
