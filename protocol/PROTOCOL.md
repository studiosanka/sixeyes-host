# The SixEyes host protocol (version 1)

How a computer or phone talks to the arm's Base board. The same messages travel over USB and Bluetooth.

The machine-readable source of truth is [messages.yaml](messages.yaml). If this page and the YAML disagree, the YAML is right.

## The idea in plain words

1. The host says **hello**. The arm says which protocol and firmware it has and what it can do.
2. **Only one source is in control** at a time: the phone (Bluetooth) or the computer (USB). The other one can only listen.
3. The arm starts **unhomed** and will not move. The host sends **home**, and the arm finds its zero position and becomes **ready**.
4. The host sends **targets** (where each joint should go). The arm moves there safely, within limits and a speed cap.
5. The arm continuously sends **state** (where each joint is) 50 to 100 times a second.
6. If the source in control goes quiet for 200 milliseconds, the arm stops. Keep sending targets or **heartbeat**.
7. **Stop** works from anywhere, any time.

Units: joint angles in **radians** at the output shaft. The gripper is **0 to 100**. Joint order: base, shoulder, elbow, wrist pitch, wrist roll, gripper. (The shoulder is two motors but one joint.)

## Messages

Host to arm:

| Type | Name | Meaning |
|---|---|---|
| 0x01 | hello | Start of conversation; carries the host's protocol version |
| 0x02 | set_control_source | Choose `ble` or `usb`. Refused while moving |
| 0x03 | home | Start homing (only from the source in control) |
| 0x04 | targets | 6 numbers: where each joint should go. Also counts as a heartbeat |
| 0x05 | stop | Hold position now |
| 0x06 | clear_fault | Clear a fault; the arm becomes unhomed |
| 0x07 | heartbeat | "Still here" when there is nothing else to send |
| 0x08–0x0A | slot_play / slot_erase / slot_write | Motions stored on the arm. **Draft**, needs the `motion_slots` capability |

Arm to host:

| Type | Name | Meaning |
|---|---|---|
| 0x80 | hello_ack | The arm's protocol and firmware version, and its capabilities |
| 0x81 | state | Streamed: time, homing state, who is in control, faults, measured joints, target joints |
| 0x82 | ack | Answer to every command: status `ok`, or the reason it was refused |

Why `state` has a *target*: it is the last target the arm accepted from whoever is in control. When the phone is driving and a laptop is only recording (Mode 2), this is how the laptop learns the "action".

---

# Reference

Everything below is for people implementing the protocol.

## Frame

```
COBS( type u8 | seq u8 | payload | crc16 u16 )  0x00
```

- Integers are little-endian. Floats are IEEE-754 32-bit, little-endian.
- `seq` counts up (wraps at 255). An `ack` repeats the `type` and `seq` of the command it answers.
- CRC-16/CCITT-FALSE (polynomial 0x1021, start value 0xFFFF) over `type`, `seq` and `payload`. Check value: CRC of the ASCII text `123456789` is `0x29B1`.
- COBS removes every `0x00` from the data so the trailing `0x00` can mark the end of a frame. A receiver ignores empty frames and drops frames with a bad CRC.
- Maximum frame: 512 encoded bytes.
- Over Bluetooth, one frame is carried in one GATT value (see [the appendix](../docs/appendix/appendix-framing.md)).

## Payloads

| Message | Payload (in order) | Bytes |
|---|---|---|
| hello | protocol_version u16 | 2 |
| set_control_source | source u8 (0 ble, 1 usb) | 1 |
| home, stop, clear_fault, heartbeat | none | 0 |
| targets | joints f32 × 6 | 24 |
| slot_play, slot_erase | slot u8 | 1 |
| slot_write | slot u8, index u16, dt_ms u16, joints f32 × 6 | 29 |
| hello_ack | protocol_version u16, fw_major u8, fw_minor u8, fw_patch u8, capabilities u16 | 7 |
| state | t_ms u32, homing_state u8, control_source u8, faults u16, measured f32 × 6, target f32 × 6 | 56 |
| ack | ref_type u8, ref_seq u8, status u8 | 3 |

## Values

| homing_state | | status | |
|---|---|---|---|
| 0 | unhomed | 0 | ok |
| 1 | homing | 1 | bad_version |
| 2 | ready | 2 | not_homed |
| 3 | fault | 3 | not_in_control |
| | | 4 | bad_args |
| | | 5 | faulted |
| | | 6 | unsupported |
| | | 7 | busy |

Capability bits: 0 homing, 1 ble, 2 echo_targets, 3 motion_slots, 4 hw_estop.
Fault bits: 0 hw_estop, 1 watchdog, 2 joint_limit, 3 stall, 4 bus_lost, 5 homing_failed.

## Rules the arm must follow

1. **Hello first.** `hello_ack` is always sent, even on a version mismatch, so the host can tell the user which side to update. A mismatch is acked `bad_version` and the state stream does not start.
2. **One source in control.** `home`, `targets`, `heartbeat` and `slot_*` from the other source are refused with `not_in_control`. `hello`, `stop`, `clear_fault` and `set_control_source` are accepted from either.
3. **Switching is explicit.** `set_control_source` is refused with `busy` while any joint is moving or homing, and it disarms the watchdog.
4. **No motion until ready.** `targets` while unhomed or homing is refused `not_homed`; while faulted, `faulted`.
5. **Limits.** Targets are clamped to the joint limits (the `joint_limit` fault bit is set while clamping) and speed-limited. Non-finite numbers are refused `bad_args`.
6. **Watchdog.** After the first `targets` or `heartbeat` from the source in control, 200 ms without either makes the arm hold its position and set the `watchdog` fault bit. The bit clears at the next `targets` or `heartbeat`.
7. **Stop** holds position and aborts homing (back to unhomed). If the arm was ready it stays ready.
8. **Hardware e-stop** overrides everything: state `fault`, fault bit `hw_estop`. `clear_fault` is refused `faulted` while the button is held; once released it returns the arm to `unhomed`.
9. **State stream** runs at 50–100 Hz to every connected host that said hello, USB always.
10. **Echo.** `state.target` is the last target accepted from the source in control, so a listener on the other transport can record it.

These rules are executable in [python/tests/test_sim.py](../python/tests/test_sim.py).
