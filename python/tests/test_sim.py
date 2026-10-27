"""The simulator's rules, with virtual time. These are the behaviours the real firmware must match."""
import math
import unittest

from sixeyes_host import _protocol as p
from sixeyes_host.codec import FrameParser, encode_frame
from sixeyes_host.sim import LIMITS, SimArm


class Host:
    """A bare-bones host talking to one port of a SimArm."""

    def __init__(self, arm, port="usb"):
        self.arm, self.port, self.parser, self.seq, self.states, self.acks = arm, port, FrameParser(), 0, [], []

    def _drain(self):
        for t, _, payload in self.parser.feed(getattr(self.arm, self.port + "_read")()):
            m = p.MESSAGES[t].decode(payload)
            (self.states if isinstance(m, p.State) else self.acks).append(m)

    def send(self, msg):
        self.seq += 1
        getattr(self.arm, self.port + "_write")(encode_frame(msg.TYPE, self.seq, msg.encode()))

    def pump(self, seconds, step=0.01):
        for _ in range(round(seconds / step)):
            self.arm.tick(step)
            self._drain()

    def status_of(self, msg):
        """Send a command, return the arm's status for it (no time passes)."""
        self.acks.clear()
        self.send(msg)
        self._drain()
        return [a.status for a in self.acks if isinstance(a, p.Ack) and a.ref_type == msg.TYPE][-1]


def ready_host():
    arm = SimArm()
    h = Host(arm)
    h.status_of(p.Hello(protocol_version=p.PROTOCOL_VERSION))
    h.status_of(p.SetControlSource(source=p.ControlSource.usb))
    h.status_of(p.Home())
    h.pump(3.0)
    return arm, h


class SimTests(unittest.TestCase):
    def test_handshake_and_state_stream(self):
        h = Host(SimArm())
        self.assertEqual(h.status_of(p.Hello(protocol_version=p.PROTOCOL_VERSION)), p.Status.ok)
        h.pump(1.0)
        self.assertAlmostEqual(len(h.states), 50, delta=3)  # 50 Hz

    def test_wrong_version_is_refused_and_no_stream(self):
        h = Host(SimArm())
        self.assertEqual(h.status_of(p.Hello(protocol_version=99)), p.Status.bad_version)
        h.pump(0.5)
        self.assertEqual(h.states, [])

    def test_no_motion_until_homed(self):
        h = Host(SimArm())
        h.status_of(p.Hello(protocol_version=1))
        h.status_of(p.SetControlSource(source=p.ControlSource.usb))
        self.assertEqual(h.status_of(p.Targets(joints=(0.1,) * 6)), p.Status.not_homed)

    def test_homing_reaches_ready(self):
        arm, h = ready_host()
        self.assertEqual(h.states[-1].homing_state, p.HomingState.ready)

    def test_only_the_source_in_control_can_move(self):
        arm, h = ready_host()
        ble = Host(arm, "ble")
        ble.status_of(p.Hello(protocol_version=1))
        self.assertEqual(ble.status_of(p.Targets(joints=(0.1,) * 6)), p.Status.not_in_control)
        self.assertEqual(ble.status_of(p.Stop()), p.Status.ok)  # stop works from anywhere

    def test_cannot_switch_source_while_moving(self):
        arm, h = ready_host()
        h.status_of(p.Targets(joints=(1.0, 0, 0, 0, 0, 0)))
        h.pump(0.1)
        self.assertEqual(h.status_of(p.SetControlSource(source=p.ControlSource.ble)), p.Status.busy)
        h.pump(1.2)
        self.assertEqual(h.status_of(p.SetControlSource(source=p.ControlSource.ble)), p.Status.ok)

    def test_targets_are_clamped_and_speed_limited(self):
        arm, h = ready_host()
        h.status_of(p.Targets(joints=(99.0, 0, 0, 0, 0, 500.0)))
        h.pump(0.02)
        self.assertEqual(h.states[-1].target[0], LIMITS[0][1])
        self.assertEqual(h.states[-1].target[5], LIMITS[5][1])
        self.assertTrue(h.states[-1].faults & p.Fault.joint_limit)
        before = arm.measured[0]
        h.status_of(p.Heartbeat())
        h.pump(0.1)
        self.assertLess(arm.measured[0] - before, 0.11)  # 1 rad/s cap over 0.1 s

    def test_nan_target_rejected(self):
        arm, h = ready_host()
        self.assertEqual(h.status_of(p.Targets(joints=(math.nan,) * 6)), p.Status.bad_args)

    def test_watchdog_stops_the_arm(self):
        arm, h = ready_host()
        h.status_of(p.Targets(joints=(2.0, 0, 0, 0, 0, 0)))
        h.pump(0.15)  # still within 200 ms: moving
        self.assertGreater(arm.measured[0], 0.0)
        h.pump(0.5)  # no feed for longer than 200 ms
        self.assertTrue(h.states[-1].faults & p.Fault.watchdog)
        held = arm.measured[0]
        h.pump(1.0)
        self.assertEqual(arm.measured[0], held)
        self.assertLess(held, 1.0)  # stopped well short of the target
        h.status_of(p.Heartbeat())
        self.assertFalse(arm.faults & p.Fault.watchdog)

    def test_heartbeat_keeps_it_alive(self):
        arm, h = ready_host()
        h.status_of(p.Targets(joints=(0.5, 0, 0, 0, 0, 0)))
        for _ in range(30):
            h.status_of(p.Heartbeat())
            h.pump(0.05)
        self.assertFalse(arm.faults & p.Fault.watchdog)
        self.assertAlmostEqual(arm.measured[0], 0.5, places=2)

    def test_stop_holds_position_and_stays_ready(self):
        arm, h = ready_host()
        h.status_of(p.Targets(joints=(2.0, 0, 0, 0, 0, 0)))
        h.pump(0.1)
        h.status_of(p.Stop())
        held = arm.measured[0]
        h.pump(1.0)
        self.assertEqual(arm.measured[0], held)
        self.assertEqual(arm.homing_state, p.HomingState.ready)

    def test_hardware_estop_needs_clear_and_rehome(self):
        arm, h = ready_host()
        arm.press_estop()
        self.assertEqual(h.status_of(p.Targets(joints=(0.1,) * 6)), p.Status.faulted)
        self.assertEqual(h.status_of(p.ClearFault()), p.Status.faulted)  # still pressed
        arm.release_estop()
        self.assertEqual(h.status_of(p.ClearFault()), p.Status.ok)
        self.assertEqual(h.status_of(p.Targets(joints=(0.1,) * 6)), p.Status.not_homed)

    def test_slots_unsupported(self):
        arm, h = ready_host()
        self.assertEqual(h.status_of(p.SlotPlay(slot=0)), p.Status.unsupported)


if __name__ == "__main__":
    unittest.main()
