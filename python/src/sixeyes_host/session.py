"""The `Arm` class: connect to an arm, send commands, read its state.

    from sixeyes_host import Arm
    with Arm("sim") as arm:          # or "COM3", "/dev/ttyACM0"
        arm.home()
        arm.move_to([0.3, 0, 0, 0, 0, 50])
        print(arm.state.measured)
"""
import math
import threading
import time

from . import _protocol as p
from .codec import FrameParser, encode_frame
from .link import Link, open_link


class ArmError(Exception):
    """Something went wrong. `str(error)` says what; `error.hint` says what to try."""

    def __init__(self, message, hint=""):
        super().__init__(message)
        self.hint = hint


# What a beginner should do about each refusal from the arm.
_REFUSALS = {
    p.Status.bad_version: ("The arm and this software speak different protocol versions.", "Update the arm's firmware or this package."),
    p.Status.not_homed: ("The arm is not homed yet.", "Run home() first (or press Home on the phone page)."),
    p.Status.not_in_control: ("Another source is in control of the arm.", "Call set_control('usb') while the arm is still."),
    p.Status.bad_args: ("The arm rejected the values you sent.", "Check the numbers are finite and in range."),
    p.Status.faulted: ("The arm has a fault.", "Check the e-stop, then call clear_fault() and home again."),
    p.Status.unsupported: ("This arm's firmware does not support that yet.", "Check arm.info.capabilities."),
    p.Status.busy: ("The arm is busy moving.", "Wait until it has stopped, then try again."),
}


class Arm:
    def __init__(self, port="sim", timeout=2.0, keepalive_hz=20):
        self._link = port if isinstance(port, Link) else open_link(port)
        self._timeout = timeout
        self._parser = FrameParser()
        self._lock = threading.Lock()
        self._cond = threading.Condition()
        self._seq = 0
        self._acks = {}
        self._state = None
        self._count = 0  # how many states have arrived
        self._info = None
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._keepalive_period = 1.0 / keepalive_hz if keepalive_hz else None
        self._beat = None
        try:
            self._handshake()
        except Exception:
            self.close()
            raise
        if self._keepalive_period:
            self._beat = threading.Thread(target=self._beat_loop, daemon=True)
            self._beat.start()

    # ------------------------------------------------------------ public
    @property
    def info(self) -> p.HelloAck:
        return self._info

    @property
    def state(self) -> p.State:
        """The newest state from the arm, or None if none has arrived yet."""
        return self._state

    def set_control(self, source):
        """Choose who moves the arm: 'usb' (this computer) or 'ble' (the phone)."""
        self._command(p.SetControlSource(source=int(p.ControlSource[source] if isinstance(source, str) else source)))

    def home(self, wait=True, timeout=30.0):
        self._command(p.Home())
        if wait:
            self.wait_for(lambda s: s.homing_state == p.HomingState.ready, timeout, "homing to finish", fresh=True)

    def send_targets(self, joints):
        if len(joints) != p.JOINT_COUNT:
            raise ArmError(f"Need {p.JOINT_COUNT} values ({', '.join(p.JOINTS)}), got {len(joints)}.")
        self._command(p.Targets(joints=tuple(float(v) for v in joints)))

    def move_to(self, joints, wait=True, tolerance=0.01, timeout=30.0):
        """Send targets (radians; gripper 0..100) and optionally wait until the arm arrives."""
        self.send_targets(joints)
        if wait:
            def arrived(s):
                stopped = p.Fault(s.faults) & (p.Fault.watchdog | p.Fault.hw_estop | p.Fault.stall)
                if stopped:
                    raise ArmError(f"The arm stopped before arriving ({stopped!r}).", "Check the e-stop and the connection, then home again if needed.")
                return all(abs(m - t) <= tolerance for m, t in zip(s.measured, s.target))
            self.wait_for(arrived, timeout, "the arm to reach its target", fresh=True)

    def stop(self):
        self._command(p.Stop())

    def clear_fault(self):
        self._command(p.ClearFault())

    def wait_for(self, predicate, timeout, what="the arm", fresh=False):
        """Wait until predicate(state) is true. fresh=True ignores states that arrived before this call,
        so a state from before your command cannot satisfy it."""
        end = time.monotonic() + timeout
        with self._cond:
            start = self._count
            while True:
                s = self._state
                if s is not None and (not fresh or self._count > start) and predicate(s):
                    return s
                left = end - time.monotonic()
                if left <= 0:
                    raise ArmError(f"Timed out waiting for {what}.", "Is the arm powered and homed? Try the monitor command.")
                self._cond.wait(min(left, 0.1))

    def close(self):
        self._running = False
        try:
            self._link.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ internals
    def _send(self, msg, wait=False):
        """Send one message. With wait=True, returns the (event, status) slot its ack will fill."""
        slot = [threading.Event(), None] if wait else None
        with self._lock:
            self._seq = (self._seq + 1) & 0xFF
            if slot:
                self._acks[(msg.TYPE, self._seq)] = slot  # registered before sending, so a fast reply is not missed
            key = (msg.TYPE, self._seq)
            self._link.write(encode_frame(msg.TYPE, self._seq, msg.encode()))
        return key, slot

    def _command(self, msg):
        key, slot = self._send(msg, wait=True)
        answered = slot[0].wait(self._timeout)
        with self._lock:
            self._acks.pop(key, None)
        if not answered:
            raise ArmError("The arm did not answer.", "Check the USB cable and that the right port is used.")
        if slot[1] != p.Status.ok:
            what, hint = _REFUSALS.get(slot[1], (f"The arm refused the command (code {slot[1]}).", ""))
            raise ArmError(what, hint)

    def _handshake(self):
        try:
            self._command(p.Hello(protocol_version=p.PROTOCOL_VERSION))
        except ArmError as e:
            if self._info is not None and self._info.protocol_version != p.PROTOCOL_VERSION:
                older = self._info.protocol_version < p.PROTOCOL_VERSION
                raise ArmError(f"Protocol mismatch: the arm speaks v{self._info.protocol_version}, this software v{p.PROTOCOL_VERSION}.",
                               "Update the arm's firmware." if older else "Update this software (pip install -U sixeyes-host).") from None
            raise
        self.wait_for(lambda s: True, self._timeout, "the first state message from the arm")

    def _read_loop(self):
        while self._running:
            try:
                data = self._link.read(0.05)
            except Exception:
                return
            for msg_type, seq, payload in self._parser.feed(data):
                self._dispatch(msg_type, seq, payload)

    def _dispatch(self, msg_type, seq, payload):
        cls = p.MESSAGES.get(msg_type)
        if cls is None:
            return
        try:
            msg = cls.decode(payload)
        except ValueError:
            return
        if isinstance(msg, p.State):
            with self._cond:
                self._state = msg
                self._count += 1
                self._cond.notify_all()
        elif isinstance(msg, p.HelloAck):
            self._info = msg
        elif isinstance(msg, p.Ack):
            with self._lock:
                slot = self._acks.get((msg.ref_type, msg.ref_seq))
            if slot:
                slot[1] = msg.status
                slot[0].set()

    def _beat_loop(self):
        # Keeps the arm's 200 ms watchdog fed while this computer is in control.
        while self._running:
            time.sleep(self._keepalive_period)
            s = self._state
            if s is not None and s.control_source == p.ControlSource.usb and s.homing_state == p.HomingState.ready:
                try:
                    self._send(p.Heartbeat())
                except Exception:
                    return
