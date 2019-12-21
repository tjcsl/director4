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
        memory: String representation of memory.

    Returns:
        The provided memory in bytes.

    """
    # TODO: Add support for memory string with units
    return int(memory)
