"""Share one connection to an arm between several users in the same program.

A serial port can only be opened once. LeRobot creates a robot object and a teleoperator object for the
same arm (Mode 2), so both ask this pool for the port: the first one opens it, the last one to let go closes it.

    arm = acquire("COM5")
    ...
    release("COM5")
"""
import threading

from .session import Arm

_lock = threading.Lock()
_entries = {}  # port -> [Arm, how many users]


def acquire(port, **kwargs) -> Arm:
    """The shared Arm for `port`, opening it if nobody has yet. Every acquire needs one release."""
    with _lock:
        entry = _entries.get(port)
        if entry is None:
            entry = _entries[port] = [Arm(port, **kwargs), 0]
        entry[1] += 1
        return entry[0]


def release(port) -> None:
    with _lock:
        entry = _entries.get(port)
        if entry is None:
            return
        entry[1] -= 1
        if entry[1] <= 0:
            del _entries[port]
            entry[0].close()


def users(port) -> int:
    """How many users hold `port` right now (0 if it is not open)."""
    with _lock:
        entry = _entries.get(port)
        return entry[1] if entry else 0
