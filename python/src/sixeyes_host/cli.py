"""`sixeyes-bringup`: check, home and move an arm from the command line. Try `sixeyes-bringup demo`."""
import argparse
import math
import sys
import time

from . import _protocol as p
from .session import Arm, ArmError


def _fmt(state):
    parts = []
    for name, m, t in zip(p.JOINTS, state.measured, state.target):
        if name == "gripper":
            parts.append(f"{name} {m:5.1f}/{t:5.1f}%")
        else:
            parts.append(f"{name} {math.degrees(m):7.1f}/{math.degrees(t):7.1f}°")
    return (f"{p.HomingState(state.homing_state).name:<7} {p.ControlSource(state.control_source).name:<3} "
            + " | ".join(parts) + (f"  FAULTS: {p.Fault(state.faults)!r}" if state.faults else ""))


def cmd_ports(args):
    from .link import list_ports

    found = list_ports()
    if not found:
        print("No serial ports found. Plug in the Base board with a data USB-C cable.")
    for name, desc in found:
        print(f"{name}\t{desc}")


def cmd_info(args):
    with Arm(args.port) as arm:
        i = arm.info
        print(f"Connected. Firmware {i.fw_major}.{i.fw_minor}.{i.fw_patch}, protocol v{i.protocol_version}")
        print("Can do:", ", ".join(c.name for c in p.Capability if i.capabilities & c) or "nothing yet")


def cmd_monitor(args):
    with Arm(args.port) as arm:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            print(_fmt(arm.state))
            time.sleep(0.25)


def cmd_home(args):
    with Arm(args.port) as arm:
        arm.set_control("usb")
        print("Homing... keep clear of the arm.")
        arm.home()
        print("Done. The arm is homed and ready.")


def cmd_jog(args):
    if args.joint not in p.JOINTS:
        raise ArmError(f"Unknown joint '{args.joint}'.", "Joints: " + ", ".join(p.JOINTS))
    i = p.JOINTS.index(args.joint)
    with Arm(args.port) as arm:
        arm.set_control("usb")
        if arm.state.homing_state != p.HomingState.ready:
            raise ArmError("The arm is not homed.", "Run the home command first.")
        goal = list(arm.state.target)
        goal[i] += args.amount if args.joint == "gripper" else math.radians(args.amount)
        arm.move_to(goal)
        print("Done.", _fmt(arm.state))


def cmd_encoders(args):
    print(f"Move each joint by hand (arm unpowered or relaxed) for {args.seconds:.0f} s...")
    lo = hi = None
    with Arm(args.port) as arm:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            m = arm.state.measured
            lo = list(m) if lo is None else [min(a, b) for a, b in zip(lo, m)]
            hi = list(m) if hi is None else [max(a, b) for a, b in zip(hi, m)]
            time.sleep(0.02)
    for name, a, b in zip(p.JOINTS, lo, hi):
        if not (math.isfinite(a) and math.isfinite(b)):
            verdict = "BAD: not a number. Check the encoder wiring."
        elif b - a > 1e-3:
            verdict = f"OK, moved {b - a:.3f}"
        else:
            verdict = "no change (move this joint to test it)"
        print(f"  {name:<12} {verdict}")


def cmd_demo(args):
    print("Demo with the built-in simulated arm (no hardware needed).")
    from .link import SimLink

    with Arm(SimLink(speed=8)) as arm:
        arm.set_control("usb")
        print("1. Homing...")
        arm.home()
        print("2. Moving the base 30° and opening the gripper halfway...")
        arm.move_to([math.radians(30), 0, 0, 0, 0, 50])
        print("3. State:", _fmt(arm.state))
        print("4. Going back to zero.")
        arm.move_to([0] * p.JOINT_COUNT)
        print("Done. Next: plug in a real arm and run `sixeyes-bringup ports`.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sixeyes-bringup", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ports", help="list USB serial ports").set_defaults(fn=cmd_ports)
    sub.add_parser("demo", help="try everything on the simulator").set_defaults(fn=cmd_demo)
    for name, fn, help_ in [("info", cmd_info, "connect and show versions"), ("monitor", cmd_monitor, "print the live state"),
                            ("home", cmd_home, "home the arm"), ("jog", cmd_jog, "move one joint a little"),
                            ("encoders", cmd_encoders, "check every encoder reads and changes")]:
        s = sub.add_parser(name, help=help_)
        s.add_argument("port", help="COM3, /dev/ttyACM0, tcp:HOST:PORT or sim")
        s.set_defaults(fn=fn)
        if name == "monitor":
            s.add_argument("--seconds", type=float, default=5)
        if name == "encoders":
            s.add_argument("--seconds", type=float, default=5)
        if name == "jog":
            s.add_argument("joint")
            s.add_argument("amount", type=float, help="degrees (percent for the gripper)")
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except ArmError as e:
        print(f"Problem: {e}", file=sys.stderr)
        if e.hint:
            print(f"Try: {e.hint}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Problem: could not open the port ({e}).", file=sys.stderr)
        print("Try: run `sixeyes-bringup ports` and check the cable.", file=sys.stderr)
        return 1
    return 0


def sim_main(argv=None):
    from .sim import SimArm, serve_tcp

    ap = argparse.ArgumentParser(prog="sixeyes-sim", description="Run a simulated arm others can connect to.")
    ap.add_argument("--tcp", type=int, default=7000, help="TCP port (default 7000); connect with tcp:127.0.0.1:7000")
    ap.add_argument("--speed", type=float, default=1.0, help="time multiplier (default 1)")
    args = ap.parse_args(argv)
    try:
        serve_tcp(SimArm(), args.tcp, args.speed)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
