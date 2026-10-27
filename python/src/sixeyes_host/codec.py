"""Frame encoding for the SixEyes link: COBS + CRC-16. No I/O here.

A frame on the wire is COBS(type | seq | payload | crc16) followed by a 0x00 byte.
COBS ("consistent overhead byte stuffing") rewrites the data so it never contains 0x00,
which lets 0x00 mark where one frame ends and the next begins.
"""


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cobs_encode(data: bytes) -> bytes:
    out = bytearray([0])  # placeholder for the first block's length byte
    code_idx, code = 0, 1
    for b in data:
        if b == 0:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
        else:
            out.append(b)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
    out[code_idx] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        code = data[i]
        if code == 0:
            raise ValueError("zero byte inside a COBS block")
        end = i + code
        if end > len(data):
            raise ValueError("COBS block runs past the end")
        out += data[i + 1:end]
        i = end
        if i < len(data) and code != 0xFF:
            out.append(0)
    return bytes(out)


def encode_frame(msg_type: int, seq: int, payload: bytes = b"") -> bytes:
    body = bytes([msg_type & 0xFF, seq & 0xFF]) + payload
    crc = crc16(body)
    return cobs_encode(body + bytes([crc & 0xFF, crc >> 8])) + b"\x00"


def decode_frame(encoded: bytes):
    """Decode one frame (without its trailing 0x00). Returns (type, seq, payload).

    Raises ValueError if the frame is damaged."""
    body = cobs_decode(encoded)
    if len(body) < 4:
        raise ValueError("frame too short")
    if crc16(body[:-2]) != body[-2] | (body[-1] << 8):
        raise ValueError("bad checksum")
    return body[0], body[1], bytes(body[2:-2])


class FrameParser:
    """Feed it bytes as they arrive; get complete, valid frames back.

    Damaged frames are dropped and counted in `errors`, so one bad byte never stops the stream."""

    MAX_FRAME = 512

    def __init__(self):
        self._buf = bytearray()
        self.errors = 0

    def feed(self, data: bytes):
        frames = []
        for b in data:
            if b != 0:
                if len(self._buf) < self.MAX_FRAME:
                    self._buf.append(b)
                continue
            if not self._buf:
                continue  # empty frame: ignore (also resyncs after noise)
            try:
                frames.append(decode_frame(bytes(self._buf)))
            except ValueError:
                self.errors += 1
            self._buf.clear()
        return frames
