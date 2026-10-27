// Frame encoding for the SixEyes link: COBS + CRC-16. Same rules as python/src/sixeyes_host/codec.py.
// Plain TypeScript (no enums), so Node and Vite can both run it.

export function crc16(data: Uint8Array): number {
  let crc = 0xffff
  for (const b of data) {
    crc ^= b << 8
    for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff
  }
  return crc
}

export function cobsEncode(data: Uint8Array): Uint8Array {
  const out: number[] = [0]
  let codeIdx = 0
  let code = 1
  for (const b of data) {
    if (b === 0) {
      out[codeIdx] = code
      codeIdx = out.length
      out.push(0)
      code = 1
    } else {
      out.push(b)
      code++
      if (code === 0xff) {
        out[codeIdx] = code
        codeIdx = out.length
        out.push(0)
        code = 1
      }
    }
  }
  out[codeIdx] = code
  return Uint8Array.from(out)
}

export function cobsDecode(data: Uint8Array): Uint8Array {
  const out: number[] = []
  let i = 0
  while (i < data.length) {
    const code = data[i]
    if (code === 0) throw new Error('zero byte inside a COBS block')
    const end = i + code
    if (end > data.length) throw new Error('COBS block runs past the end')
    for (let j = i + 1; j < end; j++) out.push(data[j])
    i = end
    if (i < data.length && code !== 0xff) out.push(0)
  }
  return Uint8Array.from(out)
}

/** One whole frame, including the trailing 0x00 delimiter. */
export function encodeFrame(type: number, seq: number, payload: Uint8Array = new Uint8Array()): Uint8Array {
  const body = new Uint8Array(payload.length + 4)
  body[0] = type & 0xff
  body[1] = seq & 0xff
  body.set(payload, 2)
  const crc = crc16(body.subarray(0, payload.length + 2))
  body[payload.length + 2] = crc & 0xff
  body[payload.length + 3] = crc >> 8
  const enc = cobsEncode(body)
  const out = new Uint8Array(enc.length + 1)
  out.set(enc)
  return out
}

export interface Frame {
  type: number
  seq: number
  payload: Uint8Array
}

/** Decode one frame without its trailing 0x00. Throws if it is damaged. */
export function decodeFrame(encoded: Uint8Array): Frame {
  const body = cobsDecode(encoded)
  if (body.length < 4) throw new Error('frame too short')
  const n = body.length
  if (crc16(body.subarray(0, n - 2)) !== (body[n - 2] | (body[n - 1] << 8))) throw new Error('bad checksum')
  return { type: body[0], seq: body[1], payload: body.slice(2, n - 2) }
}

/** Feed it bytes as they arrive; it returns complete, valid frames. Damaged frames are dropped and counted. */
export class FrameParser {
  errors = 0
  private buf: number[] = []
  private static readonly MAX_FRAME = 512

  feed(data: Uint8Array): Frame[] {
    const frames: Frame[] = []
    for (const b of data) {
      if (b !== 0) {
        if (this.buf.length < FrameParser.MAX_FRAME) this.buf.push(b)
        continue
      }
      if (this.buf.length === 0) continue
      try {
        frames.push(decodeFrame(Uint8Array.from(this.buf)))
      } catch {
        this.errors++
      }
      this.buf = []
    }
    return frames
  }
}
