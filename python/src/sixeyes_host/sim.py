"""A pretend Base board that speaks the real protocol, so software can be tested without an arm.

It follows the rules in protocol/PROTOCOL.md: one source in control, no motion until homed,
200 ms watchdog, speed and joint limits, a state stream. Time is virtual: call `tick(dt)`.

The joint limits and speeds below are PLACEHOLDERS, not the real arm's (see sixeyes_description).
"""
import math

from . import _protocol as p
from .codec import FrameParser, encode_frame

# (low, high) in radians; the gripper is 0..100.
LIMITS = [(-3.0, 3.0), (-1.5, 1.5), (-2.5, 2.5), (-1.5, 1.5), (-3.0, 3.0), (0.0, 100.0)]
MAX_SPEED = [1.0, 0.8, 1.0, 1.5, 2.0, 200.0]  # rad/s (gripper: units/s)
HOMING_ORDER = [5, 4, 3, 2, 1, 0]  # gripper and wrist first, base last, so the arm folds up
HOMING_SECONDS_PER_JOINT = 0.4
DEFAULT_CAPS = p.Capability.homing | p.Capability.ble | p.Capability.echo_targets | p.Capability.hw_estop


class _Port:
    def __init__(self, source):
        self.source = source
        self.parser = FrameParser()
        self.out = bytearray()
        self.said_hello = False


class SimArm:
    def __init__(self, capabilities=DEFAULT_CAPS, state_hz=50, fw=(0, 1, 0), protocol_version=p.PROTOCOL_VERSION):
        self.caps = capabilities
        self.state_hz = state_hz
        self.fw = fw
        self.protocol_version = protocol_version
        self.usb = _Port(p.ControlSource.usb)
        self.ble = _Port(p.ControlSource.ble)
        self.t = 0.0
        self.homing_state = p.HomingState.unhomed
        self.control = p.ControlSource.ble
        self.faults = p.Fault(0)
        self.measured = [0.0] * p.JOINT_COUNT
        self.target = [0.0] * p.JOINT_COUNT
        self._seq = 0
        self._next_state = 0.0
        self._homing_elapsed = 0.0
        self._last_feed = None  # None = watchdog not armed
        self._estop_held = False
        self._handlers = {
            p.Hello.TYPE: self._on_hello, p.SetControlSource.TYPE: self._on_set_control_source,
            p.Home.TYPE: self._on_home, p.Targets.TYPE: self._on_targets, p.Stop.TYPE: self._on_stop,
            p.ClearFault.TYPE: self._on_clear_fault, p.Heartbeat.TYPE: self._on_heartbeat,
            p.SlotPlay.TYPE: self._on_slot, p.SlotErase.TYPE: self._on_slot, p.SlotWrite.TYPE: self._on_slot,
        }

    # ------------------------------------------------------------ transports
    def usb_write(self, data):
        self._feed(self.usb, data)

    def usb_read(self):
        data, self.usb.out = bytes(self.usb.out), bytearray()
        return data

    def ble_write(self, data):
        self._feed(self.ble, data)

    def ble_read(self):
        data, self.ble.out = bytes(self.ble.out), bytearray()
        return data

    def _feed(self, port, data):
        for msg_type, seq, payload in port.parser.feed(data):
            self._handle(port, msg_type, seq, payload)

    def _send(self, port, msg):
        self._seq = (self._seq + 1) & 0xFF
        port.out += encode_frame(msg.TYPE, self._seq, msg.encode())

    def _ack(self, port, msg_type, seq, status):
        self._send(port, p.Ack(ref_type=msg_type, ref_seq=seq, status=int(status)))

    # ------------------------------------------------------------ commands
    def _handle(self, port, msg_type, seq, payload):
        cls = p.MESSAGES.get(msg_type)
        if cls is None or msg_type >= 0x80:
            return self._ack(port, msg_type, seq, p.Status.unsupported)
        try:
            msg = cls.decode(payload)
        except ValueError:
            return self._ack(port, msg_type, seq, p.Status.bad_args)
        handler = self._handlers.get(msg_type)
        status = handler(port, msg) if handler else p.Status.unsupported
        self._ack(port, msg_type, seq, status)

    def _controls(self, port):
        return port.source == self.control

    def _on_hello(self, port, msg):
        self._send(port, p.HelloAck(protocol_version=self.protocol_version, fw_major=self.fw[0], fw_minor=self.fw[1],
                                    fw_patch=self.fw[2], capabilities=int(self.caps)))
        if msg.protocol_version != self.protocol_version:
            return p.Status.bad_version
        port.said_hello = True
        return p.Status.ok

    def _moving(self):
        return self.homing_state == p.HomingState.homing or any(
            abs(m - t) > 1e-3 for m, t in zip(self.measured, self.target))

    def _on_set_control_source(self, port, msg):
        if msg.source not in (p.ControlSource.ble, p.ControlSource.usb):
            return p.Status.bad_args
        if msg.source == self.control:
            return p.Status.ok
        if self._moving():
            return p.Status.busy
        self.control = p.ControlSource(msg.source)
        self._last_feed = None
        return p.Status.ok

    def _guard(self, port):
        """Common checks for commands that need control. Returns a Status or None if fine."""
        if not self._controls(port):
            return p.Status.not_in_control
        if self.homing_state == p.HomingState.fault:
            return p.Status.faulted
        return None

    def _on_home(self, port, msg):
        bad = self._guard(port)
        if bad is not None:
            return bad
        if self.homing_state == p.HomingState.homing:
            return p.Status.busy
        self.homing_state = p.HomingState.homing
        self._homing_elapsed = 0.0
        self.target = list(self.measured)
        return p.Status.ok

    def _on_targets(self, port, msg):
        bad = self._guard(port)
        if bad is not None:
            return bad
        if self.homing_state != p.HomingState.ready:
            return p.Status.not_homed
        if not all(math.isfinite(v) for v in msg.joints):
            return p.Status.bad_args
        clamped = False
        new = []
        for v, (lo, hi) in zip(msg.joints, LIMITS):
            c = min(max(v, lo), hi)
            clamped |= c != v
            new.append(c)
        self.target = new
        self._set_fault(p.Fault.joint_limit, clamped)
        self._feed_watchdog()
        return p.Status.ok

    def _on_heartbeat(self, port, msg):
        if not self._controls(port):
            return p.Status.not_in_control
        self._feed_watchdog()
        return p.Status.ok

    def _on_stop(self, port, msg):
        self.target = list(self.measured)
        if self.homing_state == p.HomingState.homing:
            self.homing_state = p.HomingState.unhomed
        return p.Status.ok

    def _on_clear_fault(self, port, msg):
        if self._estop_held:
            return p.Status.faulted
        self.faults = p.Fault(0)
        self.homing_state = p.HomingState.unhomed
        self._last_feed = None
        return p.Status.ok

    def _on_slot(self, port, msg):
        return p.Status.unsupported  # motion slots are not simulated

    # ------------------------------------------------------------ hardware events (for tests)
    def press_estop(self):
        self._estop_held = True
        self.faults |= p.Fault.hw_estop
        self.homing_state = p.HomingState.fault
        self.target = list(self.measured)

    def release_estop(self):
        self._estop_held = False
        self.faults &= ~p.Fault.hw_estop

    # ------------------------------------------------------------ time
    def _set_fault(self, flag, on):
        self.faults = (self.faults | flag) if on else (self.faults & ~flag)

    def _feed_watchdog(self):
        self._last_feed = self.t
        self._set_fault(p.Fault.watchdog, False)

    def tick(self, dt, speed=1.0):
        """Advance `dt` seconds. `speed` > 1 makes motion and homing faster, but not the clock or watchdog."""
        self.t += dt
        if self.homing_state == p.HomingState.homing:
            self._homing_elapsed += dt * speed
            if self._homing_elapsed >= HOMING_SECONDS_PER_JOINT * len(HOMING_ORDER):
                self.measured = [0.0] * p.JOINT_COUNT
                self.target = [0.0] * p.JOINT_COUNT
                self.homing_state = p.HomingState.ready
        elif self.homing_state == p.HomingState.ready:
            if self._last_feed is not None and self.t - self._last_feed > p.WATCHDOG_MS / 1000:
                self.target = list(self.measured)  # stop where we are
                self._set_fault(p.Fault.watchdog, True)
                self._last_feed = None
            for i, (m, t) in enumerate(zip(self.measured, self.target)):
                step = MAX_SPEED[i] * dt * speed
                self.measured[i] = t if abs(t - m) <= step else m + math.copysign(step, t - m)
        period = 1.0 / self.state_hz
        while self.t >= self._next_state:
            self._next_state += period
            state = p.State(t_ms=int(self.t * 1000) & 0xFFFFFFFF, homing_state=int(self.homing_state),
                            control_source=int(self.control), faults=int(self.faults),
                            measured=tuple(self.measured), target=tuple(self.target))
            for port in (self.usb, self.ble):
                if port.said_hello:
                    self._send(port, state)


def serve_tcp(arm, port, speed=1.0):
    """Offer the simulated arm's USB side over TCP (for other programs). Blocks; one client at a time."""
    import socket
    import time

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    print(f"Simulated arm listening on tcp:127.0.0.1:{port}  (Ctrl+C to stop)")
    while True:
        conn, _ = server.accept()
        conn.settimeout(0.005)
        last = time.monotonic()
        try:
            while True:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    arm.usb_write(data)
                except socket.timeout:
                    pass
                now = time.monotonic()
                arm.tick(now - last, speed)
                last = now
                out = arm.usb_read()
                if out:
                    conn.sendall(out)
        except OSError:
            pass
        finally:
            conn.close()
            arm.usb.said_hello = False
