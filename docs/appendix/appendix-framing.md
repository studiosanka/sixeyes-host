# Appendix: why the frames look the way they do

## COBS and CRC

USB serial is a stream of bytes with no boundaries. A host can start reading in the middle of a message, or lose a byte. We need a way to find where a message starts and to notice damage.

- **COBS** (Consistent Overhead Byte Stuffing) rewrites the bytes so none is `0x00`. The `0x00` after each frame is then an unambiguous "end of message". Cost: at most one extra byte per 254. Resynchronising after noise is one rule: wait for the next `0x00`.
- **CRC-16/CCITT-FALSE** detects damaged frames. It is common, easy to write in any language, and its check value (`0x29B1` for `123456789`) is on every list of test vectors.
- Alternatives we did not pick: a length prefix (loses sync permanently after one dropped byte), JSON lines (the old Alpha/Beta protocol; slow to parse on a microcontroller and ambiguous for floats), SLIP (similar to COBS but the worst case doubles the size).

## Same frames over Bluetooth

The phone sends exactly the same frame in a GATT write; the arm notifies state the same way. Over BLE a transport already delivers whole values, so the trailing `0x00` is harmless but not needed.

The `state` frame is about 62 bytes. The default BLE payload is only 20 bytes, so either the connection negotiates a larger MTU (Android Chrome normally does, but **check this on hardware**) or the firmware sends a shorter state to BLE clients. This is an open question for `FIRMWARE_HANDOFF.md`.

## Floats

Joint values are 32-bit floats: simple, no scaling constants to get wrong, and the ESP32-C6 and every host handle them natively. At 6 floats × 50 Hz the link is far from busy.

## Changing the protocol

1. Edit `protocol/messages.yaml` (bump `protocol_version` if old code would misread the change).
2. Run `python protocol/generate.py`. It rewrites the C header, the Python and TypeScript modules and the test vectors.
3. Update `protocol/PROTOCOL.md`.
4. Run the tests in all three languages. CI refuses to merge if generated files are stale.
