// Checks the C++ codec against the shared golden vectors (generated from protocol/messages.yaml).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "sixeyes/codec.hpp"
#include "sixeyes_protocol.h"
#include "test_vectors.inc"

static int g_failures = 0;
#define CHECK(cond)                                                      \
  do {                                                                   \
    if (!(cond)) {                                                       \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);        \
      g_failures++;                                                      \
    }                                                                    \
  } while (0)

static std::vector<uint8_t> from_hex(const char *s) {
  std::vector<uint8_t> out;
  for (size_t i = 0; s[i] && s[i + 1]; i += 2) {
    const char pair[3] = {s[i], s[i + 1], 0};
    out.push_back(static_cast<uint8_t>(std::strtoul(pair, nullptr, 16)));
  }
  return out;
}

int main() {
  using namespace sixeyes;

  for (const auto &v : COBS_VECTORS) {
    const auto raw = from_hex(v.raw), enc = from_hex(v.encoded);
    CHECK(cobs_encode(raw.data(), raw.size()) == enc);
    std::vector<uint8_t> dec;
    CHECK(cobs_decode(enc.data(), enc.size(), dec) && dec == raw);
  }

  for (size_t n : {253u, 254u, 255u, 256u, 600u}) {
    const std::vector<uint8_t> sevens(n, 7), zeros(n, 0);
    for (const auto *d : {&sevens, &zeros}) {
      const auto enc = cobs_encode(d->data(), d->size());
      std::vector<uint8_t> dec;
      CHECK(!std::memchr(enc.data(), 0, enc.size()));
      CHECK(cobs_decode(enc.data(), enc.size(), dec) && dec == *d);
    }
  }

  for (const auto &v : CRC_VECTORS) {
    const auto data = from_hex(v.data);
    CHECK(crc16(data.data(), data.size()) == v.crc);
  }

  for (const auto &v : FRAME_VECTORS) {
    const auto payload = from_hex(v.payload), frame = from_hex(v.frame);
    CHECK(encode_frame(static_cast<uint8_t>(v.type), static_cast<uint8_t>(v.seq), payload.data(), payload.size()) == frame);
    Frame f;
    CHECK(decode_frame(frame.data(), frame.size() - 1, f));
    CHECK(f.type == v.type && f.seq == v.seq && f.payload == payload);
  }

  {  // parser: junk, a split frame, a corrupt frame, then a good one
    const auto good = encode_frame(SIXEYES_MSG_HEARTBEAT, 1, nullptr, 0);
    auto bad = encode_frame(SIXEYES_MSG_STOP, 2, nullptr, 0);
    bad[2] ^= 0xFF;
    FrameParser parser;
    std::vector<Frame> out;
    const uint8_t junk[] = {5, 5, 0};
    parser.feed(junk, sizeof(junk), out);
    parser.feed(good.data(), 2, out);
    CHECK(out.empty());
    parser.feed(good.data() + 2, good.size() - 2, out);
    parser.feed(bad.data(), bad.size(), out);
    parser.feed(good.data(), good.size(), out);
    CHECK(out.size() == 2 && out[0].type == SIXEYES_MSG_HEARTBEAT && out[1].seq == 1);
    CHECK(parser.errors == 2);
  }

  {  // the generated C header packs to the same bytes as the Python reference
    sixeyes_targets_t t = {{0.0f, 0.5f, -0.5f, 1.0f, 0.25f, 50.0f}};
    uint8_t buf[SIXEYES_SIZE_TARGETS];
    CHECK(sixeyes_targets_pack(&t, buf) == SIXEYES_SIZE_TARGETS);
    for (const auto &v : FRAME_VECTORS) {
      if (v.type != SIXEYES_MSG_TARGETS) continue;
      CHECK(from_hex(v.payload) == std::vector<uint8_t>(buf, buf + sizeof(buf)));
    }
    sixeyes_targets_t back;
    CHECK(sixeyes_targets_unpack(buf, sizeof(buf), &back) && back.joints[5] == 50.0f);
    CHECK(!sixeyes_targets_unpack(buf, sizeof(buf) - 1, &back));
  }

  if (g_failures) {
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
  }
  std::printf("all C++ codec checks passed\n");
  return 0;
}
