"""The Arm class against the simulator (a real background thread, sped up)."""
import math
import unittest

from sixeyes_host import Arm, ArmError, HomingState
from sixeyes_host.link import SimLink
from sixeyes_host.sim import SimArm


class SessionTests(unittest.TestCase):
    def test_connect_home_move(self):
        with Arm(SimLink(speed=10)) as arm:
            self.assertEqual(arm.info.fw_major, 0)
            arm.set_control("usb")
            arm.home()
            self.assertEqual(arm.state.homing_state, HomingState.ready)
            arm.move_to([0.4, 0, 0, 0, 0, 50.0])
            self.assertAlmostEqual(arm.state.measured[0], 0.4, delta=0.02)

    def test_moving_before_homing_gives_a_friendly_error(self):
        with Arm(SimLink(speed=10)) as arm:
            arm.set_control("usb")
            with self.assertRaises(ArmError) as cm:
                arm.send_targets([0.1] * 6)
            self.assertIn("not homed", str(cm.exception))
            self.assertIn("home()", cm.exception.hint)

    def test_not_in_control_error(self):
        with Arm(SimLink(speed=10)) as arm:
            with self.assertRaises(ArmError) as cm:
                arm.home()  # the arm starts under the phone's control (ble)
            self.assertIn("control", str(cm.exception))

    def test_version_mismatch_is_explained(self):
        link = SimLink(SimArm(protocol_version=99))
        with self.assertRaises(ArmError) as cm:
            Arm(link)
        self.assertIn("mismatch", str(cm.exception))

    def test_keepalive_holds_a_long_move(self):
        # A 1 rad/s joint takes ~1 s to move 1 rad: longer than the 200 ms watchdog.
        with Arm(SimLink(speed=1)) as arm:
            arm.set_control("usb")
            arm._link.arm.homing_state = HomingState.ready  # skip the 2.4 s homing; not what is tested here
            arm.send_targets([1.0, 0, 0, 0, 0, 0])
            arm.wait_for(lambda s: abs(s.measured[0] - s.target[0]) < 0.01, 5, "the move")
            self.assertFalse(arm.state.faults)


if __name__ == "__main__":
    unittest.main()
