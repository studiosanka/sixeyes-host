// Run with: node --test protocol/ts/codec.test.ts   (Node 22.18+ or 24 runs .ts directly)
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { cobsDecode, cobsEncode, crc16, decodeFrame, encodeFrame, FrameParser } from './codec.ts'
import { decodeState, decodeTargets, encodeState, encodeTargets, MSG } from '../generated/messages.ts'

const hex = (s: string) => Uint8Array.from(s.match(/../g) ?? [], (h) => parseInt(h, 16))
const toHex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
const vectors = JSON.parse(readFileSync(new URL('../test_vectors.json', import.meta.url), 'utf8'))

test('cobs vectors', () => {
  for (const v of vectors.cobs) {
    assert.equal(toHex(cobsEncode(hex(v.raw))), v.encoded)
    assert.equal(toHex(cobsDecode(hex(v.encoded))), v.raw)
  }
})

test('cobs long runs round trip', () => {
  for (const n of [253, 254, 255, 256, 600]) {
    for (const data of [new Uint8Array(n).fill(7), new Uint8Array(n)]) {
      const enc = cobsEncode(data)
      assert.ok(!enc.includes(0))
      assert.deepEqual(cobsDecode(enc), data)
    }
  }
})

test('crc vectors', () => {
  for (const v of vectors.crc) assert.equal(crc16(hex(v.data)), parseInt(v.crc, 16))
})

test('frame vectors match the Python reference byte for byte', () => {
  for (const v of vectors.frames) {
    const frame = encodeFrame(v.type, v.seq, hex(v.payload))
    assert.equal(toHex(frame), v.frame)
    const d = decodeFrame(frame.subarray(0, frame.length - 1))
    assert.equal(d.type, v.type)
    assert.equal(d.seq, v.seq)
    assert.equal(toHex(d.payload), v.payload)
  }
})

test('parser survives noise and splits frames', () => {
  const good = encodeFrame(MSG.heartbeat, 1)
  const bad = encodeFrame(MSG.stop, 2).slice()
  bad[2] ^= 0xff
  const p = new FrameParser()
  assert.deepEqual(p.feed(Uint8Array.from([5, 5, 0, ...good.subarray(0, 2)])), [])
  const out = p.feed(Uint8Array.from([...good.subarray(2), ...bad, ...good]))
  assert.deepEqual(out.map((f) => [f.type, f.seq]), [[MSG.heartbeat, 1], [MSG.heartbeat, 1]])
  assert.equal(p.errors, 2)
})

test('generated messages round trip and match the Python layout', () => {
  const t = { joints: [0, 0.5, -0.5, 1, 0.25, 50] }
  assert.deepEqual(decodeTargets(encodeTargets(t)), t)
  const targetsVector = vectors.frames.find((f: { type: number }) => f.type === MSG.targets)
  assert.equal(toHex(encodeTargets(t)), targetsVector.payload)
  const s = { t_ms: 123456, homing_state: 2, control_source: 1, faults: 5, measured: [1, 1, 1, 1, 1, 1], target: [2, 2, 2, 2, 2, 2] }
  assert.deepEqual(decodeState(encodeState(s)), s)
  assert.throws(() => decodeTargets(new Uint8Array(3)))
})
