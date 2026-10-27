# Getting started

## 1. Install

You need Python 3.9 or newer.

```
cd python
pip install -e .
```

## 2. Try the simulator

```
sixeyes-bringup demo
```

The simulated arm homes, moves its base 30°, opens the gripper halfway and returns. No hardware needed.

## 3. Write your own first script

```python
import math
from sixeyes_host import Arm

with Arm("sim") as arm:
    arm.set_control("usb")
    arm.home()
    arm.move_to([math.radians(45), 0, 0, 0, 0, 0])
    print(arm.state.measured)
```

Things that can go wrong give a message that says what to do next, for example *"The arm is not homed yet. Run home() first."*

## 4. Use a real arm

The arm's firmware speaks this protocol, but this has not been tried on a real arm yet, so expect rough edges:

1. Plug the Base board in with a USB-C **data** cable.
2. `sixeyes-bringup ports` shows its port name (like `COM3`).
3. `sixeyes-bringup info COM3` checks the connection and versions.
4. `sixeyes-bringup home COM3` homes it. Keep clear of the arm.

## Words you might meet

- **Homing:** the arm moves each joint to a known stop to learn where zero is. Nothing else moves until this is done.
- **Control source:** who is allowed to move the arm: the phone or this computer. Only one at a time.
- **Radians:** angles as a number. 3.14 radians is 180°. The tool `jog` uses degrees to be friendlier.

More depth: [technical notes](appendix/).
