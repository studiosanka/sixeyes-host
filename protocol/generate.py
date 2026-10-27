#!/usr/bin/env python3
"""Generate the C, Python and TypeScript protocol code from messages.yaml.

    python protocol/generate.py            write the generated files
    python protocol/generate.py --check    exit 1 if any generated file is out of date (used by CI)

Needs PyYAML (`pip install pyyaml`). Uses the Python codec in python/src to build the test vectors.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "protocol" / "messages.yaml"
OUT_C = ROOT / "protocol" / "generated" / "sixeyes_protocol.h"
OUT_TS = ROOT / "protocol" / "generated" / "messages.ts"
OUT_PY = ROOT / "python" / "src" / "sixeyes_host" / "_protocol.py"
OUT_VEC = ROOT / "protocol" / "test_vectors.json"
OUT_VEC_INC = ROOT / "core" / "tests" / "test_vectors.inc"

BANNER = "GENERATED from protocol/messages.yaml by protocol/generate.py. Do not edit by hand."

# type -> (struct char, byte size, C type, TS DataView getter/setter suffix)
TYPES = {
    "u8": ("B", 1, "uint8_t", "Uint8"),
    "u16": ("H", 2, "uint16_t", "Uint16"),
    "u32": ("I", 4, "uint32_t", "Uint32"),
    "f32": ("f", 4, "float", "Float32"),
}


FLAG_NAMES = {"capabilities": ("Capability", "CAP"), "faults": ("Fault", "FAULT")}


def camel(name):
    return "".join(p.capitalize() for p in name.split("_"))


def load():
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    ids = {}
    for name, m in spec["messages"].items():
        m.setdefault("fields", [])
        if m["id"] in ids:
            raise SystemExit(f"duplicate message id 0x{m['id']:02X}: {name} and {ids[m['id']]}")
        ids[m["id"]] = name
        for f in m["fields"]:
            if f["type"] not in TYPES:
                raise SystemExit(f"{name}.{f['name']}: unknown type {f['type']}")
    return spec


def size_of(msg):
    return sum(TYPES[f["type"]][1] * f.get("count", 1) for f in msg["fields"])


# ---------------------------------------------------------------- Python
def gen_py(spec):
    o = [f'"""{BANNER}"""', "from dataclasses import dataclass", "from enum import IntEnum, IntFlag", "import struct", ""]
    o.append(f"PROTOCOL_VERSION = {spec['protocol_version']}")
    o.append(f"JOINTS = {tuple(spec['joints'])!r}")
    o.append(f"JOINT_COUNT = {len(spec['joints'])}")
    for k, v in spec["constants"].items():
        o.append(f"{k.upper()} = {v}")
    for k, v in spec["ble"].items():
        o.append(f"BLE_{k.upper()} = {v!r}")
    o.append("")
    for ename, members in spec["enums"].items():
        o += [f"class {camel(ename)}(IntEnum):"] + [f"    {n} = {v}" for n, v in members.items()] + [""]
    for fname, bits in spec["flags"].items():
        cls = FLAG_NAMES[fname][0]
        o += [f"class {cls}(IntFlag):"] + [f"    {n} = 1 << {b}" for n, b in bits.items()] + [""]
    o += ["", "class Message:", "    TYPE = 0", "", ""]
    names = []
    for name, m in spec["messages"].items():
        cls = camel(name)
        names.append(cls)
        fmt = "<" + "".join(TYPES[f["type"]][0] * f.get("count", 1) for f in m["fields"])
        o += ["@dataclass(frozen=True)", f"class {cls}(Message):", f'    """{m["doc"].strip()}"""', f"    TYPE = 0x{m['id']:02X}"]
        o.append(f'    FMT = "{fmt}"')
        for f in m["fields"]:
            if "count" in f:
                o.append(f"    {f['name']}: tuple = (0.0,) * {f['count']}")
            else:
                o.append(f"    {f['name']}: {'float' if f['type'] == 'f32' else 'int'} = 0")
        flat = []
        for f in m["fields"]:
            flat += [f"self.{f['name']}"] if "count" not in f else [f"*self.{f['name']}"]
        o += ["", "    def encode(self) -> bytes:", f"        return struct.pack(self.FMT, {', '.join(flat)})" if flat else "        return b''", ""]
        o += ["    @classmethod", "    def decode(cls, payload: bytes):", "        if len(payload) != struct.calcsize(cls.FMT):",
              f'            raise ValueError("{name}: expected %d bytes, got %d" % (struct.calcsize(cls.FMT), len(payload)))']
        if not m["fields"]:
            o += ["        return cls()", "", ""]
            continue
        o.append("        v = struct.unpack(cls.FMT, payload)")
        args, i = [], 0
        for f in m["fields"]:
            n = f.get("count")
            if n:
                args.append(f"{f['name']}=v[{i}:{i + n}]")
                i += n
            else:
                args.append(f"{f['name']}=v[{i}]")
                i += 1
        o += [f"        return cls({', '.join(args)})", "", ""]
    o.append("MESSAGES = {m.TYPE: m for m in (" + ", ".join(names) + ",)}")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------- C
def gen_c(spec):
    p = "SIXEYES_"
    o = [f"/* {BANNER} */", "#ifndef SIXEYES_PROTOCOL_H", "#define SIXEYES_PROTOCOL_H", "",
         "#include <stdbool.h>", "#include <stddef.h>", "#include <stdint.h>", "#include <string.h>", "",
         "/* Little-endian host assumed (ESP32, x86, ARM). Floats are IEEE-754 binary32. */", "",
         f"#define {p}PROTOCOL_VERSION {spec['protocol_version']}",
         f"#define {p}JOINT_COUNT {len(spec['joints'])}"]
    for k, v in spec["constants"].items():
        o.append(f"#define {p}{k.upper()} {v}")
    for k, v in spec["ble"].items():
        o.append(f'#define {p}BLE_{k.upper()} ' + (f'"{v}"' if isinstance(v, str) else str(v)))
    o.append("")
    for i, j in enumerate(spec["joints"]):
        o.append(f"#define {p}JOINT_{j.upper()} {i}")
    o.append("")
    for ename, members in spec["enums"].items():
        for n, v in members.items():
            o.append(f"#define {p}{ename.upper()}_{n.upper()} {v}")
    for fname, bits in spec["flags"].items():
        for n, b in bits.items():
            o.append(f"#define {p}{FLAG_NAMES[fname][1]}_{n.upper()} (1u << {b})")
    o += ["", "/* Message type bytes */"]
    for name, m in spec["messages"].items():
        o.append(f"#define {p}MSG_{name.upper()} 0x{m['id']:02X}")
    o += ["", "/* Payload sizes in bytes */"]
    for name, m in spec["messages"].items():
        o.append(f"#define {p}SIZE_{name.upper()} {size_of(m)}")
    o.append("")
    for name, m in spec["messages"].items():
        if not m["fields"]:
            continue
        t = f"sixeyes_{name}_t"
        o.append(f"/* {m['doc'].strip()} */")
        o.append("typedef struct {")
        for f in m["fields"]:
            ct = TYPES[f["type"]][2]
            o.append(f"    {ct} {f['name']}" + (f"[{f['count']}]" if "count" in f else "") + ";")
        o.append(f"}} {t};")
        pack, unpack = [], []
        off = 0
        for f in m["fields"]:
            n, sz = f.get("count", 1), TYPES[f["type"]][1]
            ct = TYPES[f["type"]][2]
            pack.append(f"    memcpy(out + {off}, &m->{f['name']}, {n * sz});")
            unpack.append(f"    memcpy(&m->{f['name']}, in + {off}, {n * sz});")
            off += n * sz
        o += [f"static inline size_t sixeyes_{name}_pack(const {t} *m, uint8_t *out) {{"] + pack + [f"    return {p}SIZE_{name.upper()};", "}"]
        o += [f"static inline bool sixeyes_{name}_unpack(const uint8_t *in, size_t len, {t} *m) {{",
              f"    if (len != {p}SIZE_{name.upper()}) return false;"] + unpack + ["    return true;", "}", ""]
    o.append("#endif /* SIXEYES_PROTOCOL_H */")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------- TypeScript
def gen_ts(spec):
    o = [f"// {BANNER}", "// Plain TypeScript with no enums, so Node can run it directly.", ""]
    o.append(f"export const PROTOCOL_VERSION = {spec['protocol_version']}")
    o.append(f"export const JOINTS = {json.dumps(spec['joints'])} as const")
    for k, v in spec["constants"].items():
        o.append(f"export const {k.upper()} = {v}")
    o.append("export const BLE = { " + ", ".join(f"{camel(k)[0].lower() + camel(k)[1:]}: {json.dumps(v)}" for k, v in spec["ble"].items()) + " } as const")
    o.append("")
    for ename, members in spec["enums"].items():
        o.append(f"export const {camel(ename)} = {{ " + ", ".join(f"{n}: {v}" for n, v in members.items()) + " } as const")
    for fname, bits in spec["flags"].items():
        o.append(f"export const {FLAG_NAMES[fname][0]} = {{ " + ", ".join(f"{n}: {1 << b}" for n, b in bits.items()) + " } as const")
    o += ["", "export const MSG = { " + ", ".join(f"{n}: 0x{m['id']:02X}" for n, m in spec["messages"].items()) + " } as const", ""]
    for name, m in spec["messages"].items():
        cls = camel(name)
        o.append(f"/** {m['doc'].strip()} */")
        o.append(f"export interface {cls} {{")
        for f in m["fields"]:
            o.append(f"  {f['name']}: " + ("number[]" if "count" in f else "number"))
        o.append("}")
        o.append(f"export function encode{cls}(m: {cls}): Uint8Array {{")
        o.append(f"  const b = new Uint8Array({size_of(m)})")
        if m["fields"]:
            o.append("  const v = new DataView(b.buffer)")
        off = 0
        for f in m["fields"]:
            n, sz, suf = f.get("count", 1), TYPES[f["type"]][1], TYPES[f["type"]][3]
            le = "" if sz == 1 else ", true"  # single bytes have no byte order
            if n > 1:
                o.append(f"  for (let i = 0; i < {n}; i++) v.set{suf}({off} + i * {sz}, m.{f['name']}[i]{le})")
            else:
                o.append(f"  v.set{suf}({off}, m.{f['name']}{le})")
            off += n * sz
        o += ["  return b", "}"]
        o.append(f"export function decode{cls}(b: Uint8Array): {cls} {{")
        o.append(f"  if (b.length !== {size_of(m)}) throw new Error('{name}: expected {size_of(m)} bytes, got ' + b.length)")
        if m["fields"]:
            o.append("  const v = new DataView(b.buffer, b.byteOffset, b.byteLength)")
        o.append("  return {")
        off = 0
        for f in m["fields"]:
            n, sz, suf = f.get("count", 1), TYPES[f["type"]][1], TYPES[f["type"]][3]
            le = "" if sz == 1 else ", true"
            if n > 1:
                o.append(f"    {f['name']}: Array.from({{ length: {n} }}, (_, i) => v.get{suf}({off} + i * {sz}{le})),")
            else:
                o.append(f"    {f['name']}: v.get{suf}({off}{le}),")
            off += n * sz
        o += ["  }", "}", ""]
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------- test vectors
def gen_vectors(spec):
    sys.path.insert(0, str(ROOT / "python" / "src"))
    from sixeyes_host import codec  # noqa: E402  (needs _protocol.py written first)

    # Hand-checked, not computed: the standard COBS examples and the CRC check value.
    cobs = [("00", "0101"), ("0000", "010101"), ("11220033", "03112202" + "33"), ("11223344", "0511223344"),
            ("", "01")]
    crc = [("313233343536373839", f"{spec['crc']['check_of_123456789']:04x}"), ("", "ffff")]
    frames = []
    for name, payload in [("hello", {"protocol_version": 1}), ("home", {}),
                          ("targets", {"joints": [0.0, 0.5, -0.5, 1.0, 0.25, 50.0]}),
                          ("stop", {}), ("heartbeat", {})]:
        m = spec["messages"][name]
        import struct
        fmt = "<" + "".join(TYPES[f["type"]][0] * f.get("count", 1) for f in m["fields"])
        vals = []
        for f in m["fields"]:
            v = payload[f["name"]]
            vals += list(v) if isinstance(v, list) else [v]
        body = struct.pack(fmt, *vals) if vals else b""
        frames.append({"type": m["id"], "seq": 7, "payload": body.hex(), "frame": codec.encode_frame(m["id"], 7, body).hex()})
    return {"note": "GENERATED by protocol/generate.py. cobs and crc entries are hand-checked.", "cobs": [{"raw": r, "encoded": e} for r, e in cobs],
            "crc": [{"data": d, "crc": c} for d, c in crc], "frames": frames}


def gen_vectors_inc(v):
    o = [f"/* {BANNER} */", "static const struct { const char *raw, *encoded; } COBS_VECTORS[] = {"]
    o += [f'    {{"{c["raw"]}", "{c["encoded"]}"}},' for c in v["cobs"]] + ["};", "static const struct { const char *data; unsigned crc; } CRC_VECTORS[] = {"]
    o += [f'    {{"{c["data"]}", 0x{c["crc"]}}},' for c in v["crc"]] + ["};", "static const struct { unsigned type, seq; const char *payload, *frame; } FRAME_VECTORS[] = {"]
    o += [f'    {{{f["type"]}, {f["seq"]}, "{f["payload"]}", "{f["frame"]}"}},' for f in v["frames"]] + ["};"]
    return "\n".join(o) + "\n"


def main():
    spec = load()
    outputs = {OUT_PY: gen_py(spec), OUT_C: gen_c(spec), OUT_TS: gen_ts(spec)}
    check = "--check" in sys.argv
    stale = []

    def put(path, text):
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            stale.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")

    for path, text in outputs.items():
        put(path, text)
    vec = gen_vectors(spec)
    put(OUT_VEC, json.dumps(vec, indent=2) + "\n")
    put(OUT_VEC_INC, gen_vectors_inc(vec))
    if check and stale:
        print("Out of date (run python protocol/generate.py):", *[str(p.relative_to(ROOT)) for p in stale], sep="\n  ")
        sys.exit(1)
    print("Up to date." if not stale else "Wrote: " + ", ".join(p.name for p in stale))


if __name__ == "__main__":
    main()
