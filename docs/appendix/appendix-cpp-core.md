# Appendix: the C++ core

`core/` is a small C++17 library (no dependencies) with a plain C interface in `core/include/sixeyes.h`.

| File | Job |
|---|---|
| `codec.hpp/.cpp` | COBS, CRC-16, frame encode/decode, stream parser. Mirrors `python/.../codec.py` and `protocol/ts/codec.ts` |
| `serial.hpp/.cpp` | USB serial port: Win32 (`CreateFile`, `COMMTIMEOUTS`) and POSIX (`termios`, `poll`) |
| `stream.hpp` | `ByteStream`: anything bytes go to and come from (the serial port, or a fake in a test) |
| `session.hpp/.cpp` | `Session`: handshake, commands that wait for their answer, the state stream, the heartbeat. Same rules as the Python `Arm`. Used by `sixeyes_ros2` |
| `c_api.cpp` | `sixeyes_open`, `sixeyes_write_frame`, `sixeyes_read_frame`, ... |

The generated header `protocol/generated/sixeyes_protocol.h` has the message structs and `pack`/`unpack` functions. The firmware can copy it.

## Build and test

```
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Two tests run: `core/tests/test_codec.cpp` checks the same golden vectors as the Python and TypeScript tests, so all three agree byte for byte; `core/tests/test_session.cpp` runs the session against a scripted fake arm (handshake, version mismatch, refusals in plain words, streamed targets, heartbeat, timeouts).

## Status

Written but **not yet compiled**: the machine it was written on had no C++ compiler. CI builds it on Windows, macOS and Linux. Treat the first CI run as the first real test.

Not done: Python bindings to this library (the Python package is pure Python and works without it).
