// GENERATED from protocol/messages.yaml by protocol/generate.py. Do not edit by hand.
// Plain TypeScript with no enums, so Node can run it directly.

export const PROTOCOL_VERSION = 1
export const JOINTS = ["base", "shoulder", "elbow", "wrist_pitch", "wrist_roll", "gripper"] as const
export const WATCHDOG_MS = 200
export const STATE_RATE_HZ_MIN = 50
export const STATE_RATE_HZ_MAX = 100
export const GRIPPER_MAX = 100
export const SLOT_COUNT = 4
export const BLE = { namePrefix: "SixEyes", service: "53495845-5945-5300-0001-000000000000", rx: "53495845-5945-5300-0002-000000000000", tx: "53495845-5945-5300-0003-000000000000", chunkBytes: 20 } as const

export const HomingState = { unhomed: 0, homing: 1, ready: 2, fault: 3 } as const
export const ControlSource = { ble: 0, usb: 1 } as const
export const Status = { ok: 0, bad_version: 1, not_homed: 2, not_in_control: 3, bad_args: 4, faulted: 5, unsupported: 6, busy: 7 } as const
export const Capability = { homing: 1, ble: 2, echo_targets: 4, motion_slots: 8, hw_estop: 16 } as const
export const Fault = { hw_estop: 1, watchdog: 2, joint_limit: 4, stall: 8, bus_lost: 16, homing_failed: 32 } as const

export const MSG = { hello: 0x01, set_control_source: 0x02, home: 0x03, targets: 0x04, stop: 0x05, clear_fault: 0x06, heartbeat: 0x07, slot_play: 0x08, slot_erase: 0x09, slot_write: 0x0A, hello_ack: 0x80, state: 0x81, ack: 0x82 } as const

/** First message after connecting. Tells the arm which protocol the host speaks. */
export interface Hello {
  protocol_version: number
}
export function encodeHello(m: Hello): Uint8Array {
  const b = new Uint8Array(2)
  const v = new DataView(b.buffer)
  v.setUint16(0, m.protocol_version, true)
  return b
}
export function decodeHello(b: Uint8Array): Hello {
  if (b.length !== 2) throw new Error('hello: expected 2 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    protocol_version: v.getUint16(0, true),
  }
}

/** Choose who may move the arm (ble or usb). Refused while the arm is moving. */
export interface SetControlSource {
  source: number
}
export function encodeSetControlSource(m: SetControlSource): Uint8Array {
  const b = new Uint8Array(1)
  const v = new DataView(b.buffer)
  v.setUint8(0, m.source)
  return b
}
export function decodeSetControlSource(b: Uint8Array): SetControlSource {
  if (b.length !== 1) throw new Error('set_control_source: expected 1 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    source: v.getUint8(0),
  }
}

/** Start homing. Only accepted from the source in control. */
export interface Home {
}
export function encodeHome(m: Home): Uint8Array {
  const b = new Uint8Array(0)
  return b
}
export function decodeHome(b: Uint8Array): Home {
  if (b.length !== 0) throw new Error('home: expected 0 bytes, got ' + b.length)
  return {
  }
}

/** Joint targets. Counts as a heartbeat for the watchdog. */
export interface Targets {
  joints: number[]
}
export function encodeTargets(m: Targets): Uint8Array {
  const b = new Uint8Array(24)
  const v = new DataView(b.buffer)
  for (let i = 0; i < 6; i++) v.setFloat32(0 + i * 4, m.joints[i], true)
  return b
}
export function decodeTargets(b: Uint8Array): Targets {
  if (b.length !== 24) throw new Error('targets: expected 24 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    joints: Array.from({ length: 6 }, (_, i) => v.getFloat32(0 + i * 4, true)),
  }
}

/** Software e-stop. Hold position now. Accepted from either source, always. */
export interface Stop {
}
export function encodeStop(m: Stop): Uint8Array {
  const b = new Uint8Array(0)
  return b
}
export function decodeStop(b: Uint8Array): Stop {
  if (b.length !== 0) throw new Error('stop: expected 0 bytes, got ' + b.length)
  return {
  }
}

/** Clear a fault. The arm goes back to unhomed and must be homed again. */
export interface ClearFault {
}
export function encodeClearFault(m: ClearFault): Uint8Array {
  const b = new Uint8Array(0)
  return b
}
export function decodeClearFault(b: Uint8Array): ClearFault {
  if (b.length !== 0) throw new Error('clear_fault: expected 0 bytes, got ' + b.length)
  return {
  }
}

/** Keeps the watchdog fed while no targets are being sent. */
export interface Heartbeat {
}
export function encodeHeartbeat(m: Heartbeat): Uint8Array {
  const b = new Uint8Array(0)
  return b
}
export function decodeHeartbeat(b: Uint8Array): Heartbeat {
  if (b.length !== 0) throw new Error('heartbeat: expected 0 bytes, got ' + b.length)
  return {
  }
}

/** (draft, needs capability motion_slots) Play a motion stored on the arm. */
export interface SlotPlay {
  slot: number
}
export function encodeSlotPlay(m: SlotPlay): Uint8Array {
  const b = new Uint8Array(1)
  const v = new DataView(b.buffer)
  v.setUint8(0, m.slot)
  return b
}
export function decodeSlotPlay(b: Uint8Array): SlotPlay {
  if (b.length !== 1) throw new Error('slot_play: expected 1 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    slot: v.getUint8(0),
  }
}

/** (draft, needs capability motion_slots) Erase a stored motion. */
export interface SlotErase {
  slot: number
}
export function encodeSlotErase(m: SlotErase): Uint8Array {
  const b = new Uint8Array(1)
  const v = new DataView(b.buffer)
  v.setUint8(0, m.slot)
  return b
}
export function decodeSlotErase(b: Uint8Array): SlotErase {
  if (b.length !== 1) throw new Error('slot_erase: expected 1 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    slot: v.getUint8(0),
  }
}

/** (draft, needs capability motion_slots) Write one sample of a stored motion. */
export interface SlotWrite {
  slot: number
  index: number
  dt_ms: number
  joints: number[]
}
export function encodeSlotWrite(m: SlotWrite): Uint8Array {
  const b = new Uint8Array(29)
  const v = new DataView(b.buffer)
  v.setUint8(0, m.slot)
  v.setUint16(1, m.index, true)
  v.setUint16(3, m.dt_ms, true)
  for (let i = 0; i < 6; i++) v.setFloat32(5 + i * 4, m.joints[i], true)
  return b
}
export function decodeSlotWrite(b: Uint8Array): SlotWrite {
  if (b.length !== 29) throw new Error('slot_write: expected 29 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    slot: v.getUint8(0),
    index: v.getUint16(1, true),
    dt_ms: v.getUint16(3, true),
    joints: Array.from({ length: 6 }, (_, i) => v.getFloat32(5 + i * 4, true)),
  }
}

/** Reply to hello. Carries the arm's protocol and firmware versions and what it can do. */
export interface HelloAck {
  protocol_version: number
  fw_major: number
  fw_minor: number
  fw_patch: number
  capabilities: number
}
export function encodeHelloAck(m: HelloAck): Uint8Array {
  const b = new Uint8Array(7)
  const v = new DataView(b.buffer)
  v.setUint16(0, m.protocol_version, true)
  v.setUint8(2, m.fw_major)
  v.setUint8(3, m.fw_minor)
  v.setUint8(4, m.fw_patch)
  v.setUint16(5, m.capabilities, true)
  return b
}
export function decodeHelloAck(b: Uint8Array): HelloAck {
  if (b.length !== 7) throw new Error('hello_ack: expected 7 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    protocol_version: v.getUint16(0, true),
    fw_major: v.getUint8(2),
    fw_minor: v.getUint8(3),
    fw_patch: v.getUint8(4),
    capabilities: v.getUint16(5, true),
  }
}

/** Streamed 50-100 times a second. measured = what the encoders say. target = the last target accepted from the source in control (this is the "echo" Mode 2 records). */
export interface State {
  t_ms: number
  homing_state: number
  control_source: number
  faults: number
  measured: number[]
  target: number[]
}
export function encodeState(m: State): Uint8Array {
  const b = new Uint8Array(56)
  const v = new DataView(b.buffer)
  v.setUint32(0, m.t_ms, true)
  v.setUint8(4, m.homing_state)
  v.setUint8(5, m.control_source)
  v.setUint16(6, m.faults, true)
  for (let i = 0; i < 6; i++) v.setFloat32(8 + i * 4, m.measured[i], true)
  for (let i = 0; i < 6; i++) v.setFloat32(32 + i * 4, m.target[i], true)
  return b
}
export function decodeState(b: Uint8Array): State {
  if (b.length !== 56) throw new Error('state: expected 56 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    t_ms: v.getUint32(0, true),
    homing_state: v.getUint8(4),
    control_source: v.getUint8(5),
    faults: v.getUint16(6, true),
    measured: Array.from({ length: 6 }, (_, i) => v.getFloat32(8 + i * 4, true)),
    target: Array.from({ length: 6 }, (_, i) => v.getFloat32(32 + i * 4, true)),
  }
}

/** Answer to every command. status 0 means done, anything else says why not. */
export interface Ack {
  ref_type: number
  ref_seq: number
  status: number
}
export function encodeAck(m: Ack): Uint8Array {
  const b = new Uint8Array(3)
  const v = new DataView(b.buffer)
  v.setUint8(0, m.ref_type)
  v.setUint8(1, m.ref_seq)
  v.setUint8(2, m.status)
  return b
}
export function decodeAck(b: Uint8Array): Ack {
  if (b.length !== 3) throw new Error('ack: expected 3 bytes, got ' + b.length)
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)
  return {
    ref_type: v.getUint8(0),
    ref_seq: v.getUint8(1),
    status: v.getUint8(2),
  }
}

