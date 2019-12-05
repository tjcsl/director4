
def convert_cpu_limit(cpus: float) -> int:
    """Convert a provided 

    Args:
        cpus: Represents the number of CPUs

    Returns:
        The converted limit
    """
    # Multiply by 10^9
    # 1 CPU is equivalent to one CPU
    return int(cpus * 1E9)

def convert_memory_limit(memory: str) -> int:
    """Converts a provided memory limit with units into
        its equivalent in bytes

    Args:
        memory: Represents in a string the 

    """
    # TODO: Add support for memory string with units
    return int(memory)
