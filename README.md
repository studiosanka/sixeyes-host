# sixeyes-host

Control a [SixEyes](https://github.com/studiosanka/sixeyes) robot arm from your computer over USB.

This is the library every other SixEyes tool builds on. It also has a **simulated arm**, so you can try everything before your arm is built.

> **Work in progress.** It works against the simulator. It has not been tried on a real arm yet, because the arm's firmware does not speak this protocol yet.

## Try it in one minute

You need Python 3.9 or newer.

```
cd python
pip install -e .
sixeyes-bringup demo
```

You will see the simulated arm home itself, move, and come back.

## Use it in Python

```python
from sixeyes_host import Arm

with Arm("sim") as arm:        # for a real arm use "COM3" (Windows) or "/dev/ttyACM0" (Linux)
    arm.set_control("usb")     # this computer is now in charge
    arm.home()                 # the arm finds its zero position
    arm.move_to([0.5, 0, 0, 0, 0, 50])   # joint angles in radians, gripper 0 to 100
```

## Tools

| Command | What it does |
|---|---|
| `sixeyes-bringup ports` | Lists USB ports, so you can find your arm |
| `sixeyes-bringup home PORT` | Homes the arm |
| `sixeyes-bringup jog PORT JOINT DEGREES` | Nudges one joint |
| `sixeyes-bringup encoders PORT` | Checks every joint's sensor reads and changes |
| `sixeyes-bringup monitor PORT` | Shows live joint positions |
| `sixeyes-sim` | Runs a simulated arm other programs can connect to |

## Status

| Part | State |
|---|---|
| Protocol description | ✅ written, version 1 ([protocol/PROTOCOL.md](protocol/PROTOCOL.md)) |
| Python library, simulator, bring-up tool | ✅ works, tested on the simulator |
| TypeScript codec (used by the phone page) | ✅ works, tested |
| C++ core and session (for ROS 2) | 🚧 written, not compiled or tested yet (CI will) |
| Real arm | ⬜ firmware does not support this yet |

## More

- [Getting started](docs/getting-started.md)
- [Technical notes](docs/appendix/) (for when you want to know how it works)
- [Contributing](CONTRIBUTING.md) · Licence: Apache-2.0

Built by [Studio Sanka](https://github.com/studiosanka). Developed with AI assistance from [Claude](https://www.anthropic.com/claude) (Anthropic); the designs, decisions and review are by the Studio Sanka team.
