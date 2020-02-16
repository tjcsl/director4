# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Union


def convert_cpu_limit(cpus: float) -> int:
    """Convert a provided number of CPUs to the
    equivalent number of nano CPUs accepted by Docker.

    Args:
        cpus: Represents the full number of CPUs.

    Returns:
        The equivalent number of nano CPUs. This is
        the number accepted by Docker.

    """
    return int(cpus * 1e9)


def convert_memory_limit(memory: Union[str, int]) -> int:
    """Converts a provided memory limit with optional units into
    its equivalent in bytes.

    Args:
        memory: String or integer representation of memory limit.

    Returns:
        The provided memory in bytes.

    """

    if isinstance(memory, int):
        return memory

    # MUST be sorted by longest suffix
    suffixes = [
        ("bytes", 1),
        ("KiB", 1024),
        ("MiB", 1024 ** 2),
        ("GiB", 1024 ** 3),
        ("KB", 1000),
        ("MB", 1000 ** 2),
        ("GB", 1000 ** 3),
        ("B", 1),
        ("K", 1024),
        ("M", 1024 ** 2),
        ("G", 1024 ** 3),
        ("b", 1),
        ("k", 1000),
        ("m", 1000 ** 2),
        ("g", 1000 ** 3),
    ]

    for suffix, factor in suffixes:
        if memory.endswith(suffix):
            return factor * int(memory[: -len(suffix)].strip())

    return int(memory)
