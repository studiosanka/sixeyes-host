# Appendix: the simulator

`sixeyes_host.sim.SimArm` pretends to be the Base board. It exists so host software can be tested without an arm, and as an executable copy of the rules in `protocol/PROTOCOL.md`.

## What it does

All ten rules in PROTOCOL.md: handshake with version check, one source in control, no motion until homed, clamping and speed cap, 200 ms watchdog, stop, hardware e-stop (`press_estop()` / `release_estop()` for tests), a 50 Hz state stream, and a second "BLE" port (`ble_write` / `ble_read`) so two-source behaviour can be tested.

Homing takes 0.4 s per joint in a fixed order (gripper, wrist roll, wrist pitch, elbow, shoulder, base), then reports all joints at 0.

## What it does not do

- **Joint limits and speeds are placeholders** (`LIMITS`, `MAX_SPEED` at the top of `sim.py`). They are not the real arm's. Real values come from CAD (see `sixeyes_description`).
- Motion slots: answered `unsupported`.
- Stall detection, faults other than the watchdog, joint-limit and e-stop, and the bus-lost fault are not simulated.
- Motion is a straight speed-capped ramp. The real arm will use acceleration limits.
- It has no CAN bus and no physics.

## Ways to use it

| How | When |
|---|---|
| `Arm("sim")` | Quick scripts. The sim runs in a thread in your process |
| `Arm(SimLink(speed=8))` | Tests: motion and homing run 8× faster, but the watchdog does not |
| `SimArm()` and `tick(dt)` | Unit tests with exact, repeatable time (see `python/tests/test_sim.py`) |
| `sixeyes-sim --tcp 7000`, then `Arm("tcp:127.0.0.1:7000")` | Another program or language needs to connect |
