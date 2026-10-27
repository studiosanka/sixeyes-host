"""GENERATED from protocol/messages.yaml by protocol/generate.py. Do not edit by hand."""
from dataclasses import dataclass
from enum import IntEnum, IntFlag
import struct

PROTOCOL_VERSION = 1
JOINTS = ('base', 'shoulder', 'elbow', 'wrist_pitch', 'wrist_roll', 'gripper')
JOINT_COUNT = 6
WATCHDOG_MS = 200
STATE_RATE_HZ_MIN = 50
STATE_RATE_HZ_MAX = 100
GRIPPER_MAX = 100
SLOT_COUNT = 4
BLE_NAME_PREFIX = 'SixEyes'
BLE_SERVICE = '6ada6b7d-30c8-4228-bfbe-8cd8cdc8802a'
BLE_RX = '55c1c73e-13b6-4550-931e-7c97b68d0fe7'
BLE_TX = '1f8633d2-095c-4f4c-aeb2-3129fc594d6d'
BLE_CHUNK_BYTES = 20

class HomingState(IntEnum):
    unhomed = 0
    homing = 1
    ready = 2
    fault = 3

class ControlSource(IntEnum):
    ble = 0
    usb = 1

class Status(IntEnum):
    ok = 0
    bad_version = 1
    not_homed = 2
    not_in_control = 3
    bad_args = 4
    faulted = 5
    unsupported = 6
    busy = 7

class Capability(IntFlag):
    homing = 1 << 0
    ble = 1 << 1
    echo_targets = 1 << 2
    motion_slots = 1 << 3
    hw_estop = 1 << 4

class Fault(IntFlag):
    hw_estop = 1 << 0
    watchdog = 1 << 1
    joint_limit = 1 << 2
    stall = 1 << 3
    bus_lost = 1 << 4
    homing_failed = 1 << 5


class Message:
    TYPE = 0


@dataclass(frozen=True)
class Hello(Message):
    """First message after connecting. Tells the arm which protocol the host speaks."""
    TYPE = 0x01
    FMT = "<H"
    protocol_version: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.protocol_version)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("hello: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(protocol_version=v[0])


@dataclass(frozen=True)
class SetControlSource(Message):
    """Choose who may move the arm (ble or usb). Refused while the arm is moving."""
    TYPE = 0x02
    FMT = "<B"
    source: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.source)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("set_control_source: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(source=v[0])


@dataclass(frozen=True)
class Home(Message):
    """Start homing. Only accepted from the source in control."""
    TYPE = 0x03
    FMT = "<"

    def encode(self) -> bytes:
        return b''

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("home: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        return cls()


@dataclass(frozen=True)
class Targets(Message):
    """Joint targets. Counts as a heartbeat for the watchdog."""
    TYPE = 0x04
    FMT = "<ffffff"
    joints: tuple = (0.0,) * 6

    def encode(self) -> bytes:
        return struct.pack(self.FMT, *self.joints)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("targets: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(joints=v[0:6])


@dataclass(frozen=True)
class Stop(Message):
    """Software e-stop. Hold position now. Accepted from either source, always."""
    TYPE = 0x05
    FMT = "<"

    def encode(self) -> bytes:
        return b''

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("stop: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        return cls()


@dataclass(frozen=True)
class ClearFault(Message):
    """Clear a fault. The arm goes back to unhomed and must be homed again."""
    TYPE = 0x06
    FMT = "<"

    def encode(self) -> bytes:
        return b''

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("clear_fault: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        return cls()


@dataclass(frozen=True)
class Heartbeat(Message):
    """Keeps the watchdog fed while no targets are being sent."""
    TYPE = 0x07
    FMT = "<"

    def encode(self) -> bytes:
        return b''

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("heartbeat: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        return cls()


@dataclass(frozen=True)
class SlotPlay(Message):
    """(draft, needs capability motion_slots) Play a motion stored on the arm."""
    TYPE = 0x08
    FMT = "<B"
    slot: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.slot)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("slot_play: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(slot=v[0])


@dataclass(frozen=True)
class SlotErase(Message):
    """(draft, needs capability motion_slots) Erase a stored motion."""
    TYPE = 0x09
    FMT = "<B"
    slot: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.slot)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("slot_erase: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(slot=v[0])


@dataclass(frozen=True)
class SlotWrite(Message):
    """(draft, needs capability motion_slots) Write one sample of a stored motion."""
    TYPE = 0x0A
    FMT = "<BHHffffff"
    slot: int = 0
    index: int = 0
    dt_ms: int = 0
    joints: tuple = (0.0,) * 6

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.slot, self.index, self.dt_ms, *self.joints)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("slot_write: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(slot=v[0], index=v[1], dt_ms=v[2], joints=v[3:9])


@dataclass(frozen=True)
class HelloAck(Message):
    """Reply to hello. Carries the arm's protocol and firmware versions and what it can do."""
    TYPE = 0x80
    FMT = "<HBBBH"
    protocol_version: int = 0
    fw_major: int = 0
    fw_minor: int = 0
    fw_patch: int = 0
    capabilities: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.protocol_version, self.fw_major, self.fw_minor, self.fw_patch, self.capabilities)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("hello_ack: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(protocol_version=v[0], fw_major=v[1], fw_minor=v[2], fw_patch=v[3], capabilities=v[4])


@dataclass(frozen=True)
class State(Message):
    """Streamed 50-100 times a second. measured = what the encoders say. target = the last target accepted from the source in control (this is the "echo" Mode 2 records)."""
    TYPE = 0x81
    FMT = "<IBBHffffffffffff"
    t_ms: int = 0
    homing_state: int = 0
    control_source: int = 0
    faults: int = 0
    measured: tuple = (0.0,) * 6
    target: tuple = (0.0,) * 6

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.t_ms, self.homing_state, self.control_source, self.faults, *self.measured, *self.target)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("state: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(t_ms=v[0], homing_state=v[1], control_source=v[2], faults=v[3], measured=v[4:10], target=v[10:16])


@dataclass(frozen=True)
class Ack(Message):
    """Answer to every command. status 0 means done, anything else says why not."""
    TYPE = 0x82
    FMT = "<BBB"
    ref_type: int = 0
    ref_seq: int = 0
    status: int = 0

    def encode(self) -> bytes:
        return struct.pack(self.FMT, self.ref_type, self.ref_seq, self.status)

    @classmethod
    def decode(cls, payload: bytes):
        if len(payload) != struct.calcsize(cls.FMT):
            raise ValueError("ack: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))
        v = struct.unpack(cls.FMT, payload)
        return cls(ref_type=v[0], ref_seq=v[1], status=v[2])


MESSAGES = {m.TYPE: m for m in (Hello, SetControlSource, Home, Targets, Stop, ClearFault, Heartbeat, SlotPlay, SlotErase, SlotWrite, HelloAck, State, Ack,)}
