import json
import unittest
from pathlib import Path

from sixeyes_host import _protocol as p
from sixeyes_host.codec import FrameParser, cobs_decode, cobs_encode, crc16, decode_frame, encode_frame

VECTORS = json.loads((Path(__file__).resolve().parents[2] / "protocol" / "test_vectors.json").read_text())


class CodecTests(unittest.TestCase):
    def test_cobs_vectors(self):
        for v in VECTORS["cobs"]:
            raw, enc = bytes.fromhex(v["raw"]), bytes.fromhex(v["encoded"])
            self.assertEqual(cobs_encode(raw), enc)
            self.assertEqual(cobs_decode(enc), raw)

    def test_cobs_long_runs_round_trip(self):
        for n in (253, 254, 255, 256, 600):
            for data in (bytes([7]) * n, bytes(n), bytes(range(1, 256)) * 3):
                enc = cobs_encode(data)
                self.assertNotIn(0, enc)
                self.assertEqual(cobs_decode(enc), data)

    def test_crc_vectors(self):
        for v in VECTORS["crc"]:
            self.assertEqual(crc16(bytes.fromhex(v["data"])), int(v["crc"], 16))

    def test_frame_vectors(self):
        for v in VECTORS["frames"]:
            frame = bytes.fromhex(v["frame"])
            self.assertEqual(encode_frame(v["type"], v["seq"], bytes.fromhex(v["payload"])), frame)
            self.assertEqual(decode_frame(frame[:-1]), (v["type"], v["seq"], bytes.fromhex(v["payload"])))

    def test_parser_splits_and_survives_noise(self):
        good = encode_frame(p.Heartbeat.TYPE, 1)
        corrupt = bytearray(encode_frame(p.Stop.TYPE, 2))
        corrupt[2] ^= 0xFF
        parser = FrameParser()
        out = parser.feed(b"\x05\x05\x00" + good[:2])  # junk, then half a frame
        self.assertEqual(out, [])
        out = parser.feed(good[2:] + bytes(corrupt) + good)
        self.assertEqual([f[:2] for f in out], [(p.Heartbeat.TYPE, 1), (p.Heartbeat.TYPE, 1)])
        self.assertEqual(parser.errors, 2)  # the junk frame and the corrupt one

    def test_messages_round_trip(self):
        t = p.Targets(joints=(0.0, 0.5, -0.5, 1.0, 0.25, 50.0))
        self.assertEqual(p.Targets.decode(t.encode()), t)
        s = p.State(t_ms=123456, homing_state=2, control_source=1, faults=5, measured=(1.0,) * 6, target=(2.0,) * 6)
        self.assertEqual(p.State.decode(s.encode()), s)
        with self.assertRaises(ValueError):
            p.Targets.decode(b"\x00")


if __name__ == "__main__":
    unittest.main()
