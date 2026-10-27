import unittest

from sixeyes_host import pool
from sixeyes_host import _protocol as p


class PoolTests(unittest.TestCase):
    def tearDown(self):
        while pool.users("sim:20"):
            pool.release("sim:20")

    def test_two_users_share_one_connection(self):
        a = pool.acquire("sim:20")
        b = pool.acquire("sim:20")
        self.assertIs(a, b)
        self.assertEqual(pool.users("sim:20"), 2)

    def test_the_last_release_closes_it(self):
        a = pool.acquire("sim:20")
        pool.acquire("sim:20")
        pool.release("sim:20")
        self.assertEqual(pool.users("sim:20"), 1)
        self.assertTrue(a._running)  # still open for the other user
        pool.release("sim:20")
        self.assertEqual(pool.users("sim:20"), 0)
        self.assertFalse(a._running)

    def test_release_of_an_unknown_port_is_harmless(self):
        pool.release("never-opened")

    def test_a_new_acquire_after_closing_opens_a_fresh_connection(self):
        a = pool.acquire("sim:20")
        pool.release("sim:20")
        b = pool.acquire("sim:20")
        self.assertIsNot(a, b)

    def test_sim_speed_and_state_age(self):
        arm = pool.acquire("sim:20")
        arm.set_control("usb")
        arm.home()  # 2.4 s of homing in about 0.12 s
        self.assertEqual(arm.state.homing_state, p.HomingState.ready)
        self.assertLess(arm.state_age, 1.0)
        self.assertIs(arm.link.arm.homing_state, p.HomingState.ready)


if __name__ == "__main__":
    unittest.main()
