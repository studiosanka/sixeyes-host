"""Ways to reach an arm: a serial (USB) port, a TCP socket, or the built-in simulator.

Every link moves raw bytes. Framing lives in codec.py, meaning lives in session.py.
"""
import queue
import socket
import threading
import time


class Link:
    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def read(self, timeout: float) -> bytes:
        """Wait up to `timeout` seconds. Returns b"" if nothing arrived."""
        raise NotImplementedError

    def close(self) -> None:
        pass


class SerialLink(Link):
    def __init__(self, port: str, baud: int = 115200):
        import serial  # pyserial; imported here so the simulator works without it

        self._ser = serial.Serial(port, baud, timeout=0)
        # USB CDC ignores the baud rate, but opening the port toggles DTR; give the board a moment.
        time.sleep(0.05)

    def write(self, data: bytes) -> None:
        self._ser.write(data)

    def read(self, timeout: float) -> bytes:
        end = time.monotonic() + timeout
        while True:
            n = self._ser.in_waiting
            if n:
                return self._ser.read(n)
            if time.monotonic() >= end:
                return b""
            time.sleep(0.002)

    def close(self) -> None:
        self._ser.close()


class TcpLink(Link):
    def __init__(self, host: str, port: int):
        self._sock = socket.create_connection((host, port), timeout=3)

    def write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def read(self, timeout: float) -> bytes:
        self._sock.settimeout(max(timeout, 0.001))
        try:
            return self._sock.recv(4096)
        except socket.timeout:
            return b""
        except OSError:
            return b""

    def close(self) -> None:
        self._sock.close()


class SimLink(Link):
    """The simulated arm, running in a background thread."""

    def __init__(self, arm=None, speed: float = 1.0):
        from .sim import SimArm

        self.arm = arm or SimArm()
        self._speed = speed
        self._lock = threading.Lock()
        self._out = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        last = time.monotonic()
        while self._running:
            time.sleep(0.005)
            now = time.monotonic()
            with self._lock:
                self.arm.tick(now - last, self._speed)
                data = self.arm.usb_read()
            last = now
            if data:
                self._out.put(data)

    def write(self, data: bytes) -> None:
        with self._lock:
            self.arm.usb_write(data)

    def read(self, timeout: float) -> bytes:
        try:
            return self._out.get(timeout=timeout)
        except queue.Empty:
            return b""

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=1)


def list_ports():
    """Serial ports that look like boards: [(name, description)]."""
    from serial.tools import list_ports as lp

    return [(p.device, p.description) for p in lp.comports()]


def open_link(target: str) -> Link:
    """`sim`, `tcp:HOST:PORT`, or a serial port name such as COM3 or /dev/ttyACM0."""
    if target == "sim":
        return SimLink()
    if target.startswith("tcp:"):
        _, host, port = target.split(":")
        return TcpLink(host, int(port))
    return SerialLink(target)
