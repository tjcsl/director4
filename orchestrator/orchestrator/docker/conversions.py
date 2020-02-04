# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors


def convert_cpu_limit(cpus: float) -> int:
    """Convert a provided number of CPUs to the
    equivalent accepted by Docker.

    Args:
        cpus: Represents the number of CPUs.

    Returns:
        The converted limit that can be accepted
        by Docker.

    """
    # Multiply by 10^9
    # 1 CPU is equivalent to one CPU core
    return int(cpus * 1e9)


def convert_memory_limit(memory: str) -> int:
    """Converts a provided memory limit with units into
    its equivalent in bytes.

    Args:
        memory: String representation of memory limit.

    Returns:
        The provided memory in bytes.

    """

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
