#include <algorithm>
#include <cstring>
#include <deque>
#include <string>
#include <utility>
#include <vector>

#include "sixeyes.h"
#include "sixeyes/codec.hpp"
#include "sixeyes/serial.hpp"

namespace {
thread_local std::string g_error;
}

struct sixeyes_port {
  std::unique_ptr<sixeyes::SerialPort> serial;
  sixeyes::FrameParser parser;
  std::deque<sixeyes::Frame> pending;
};

extern "C" {

sixeyes_port *sixeyes_open(const char *name) {
  std::string err;
  auto serial = sixeyes::SerialPort::open(name ? name : "", err);
  if (!serial) {
    g_error = err;
    return nullptr;
  }
  auto *p = new sixeyes_port();
  p->serial = std::move(serial);
  return p;
}

void sixeyes_close(sixeyes_port *port) { delete port; }

int sixeyes_write_frame(sixeyes_port *port, uint8_t type, uint8_t seq, const uint8_t *payload, size_t len) {
  if (!port) {
    g_error = "no port";
    return -1;
  }
  const std::vector<uint8_t> bytes = sixeyes::encode_frame(type, seq, payload, len);
  size_t sent = 0;
  while (sent < bytes.size()) {
    const long r = port->serial->write(bytes.data() + sent, bytes.size() - sent);
    if (r < 0) {
      g_error = "write failed (was the cable unplugged?)";
      return -1;
    }
    sent += static_cast<size_t>(r);
  }
  return 0;
}

int sixeyes_read_frame(sixeyes_port *port, int timeout_ms, uint8_t *type, uint8_t *seq, uint8_t *payload, size_t cap,
                       size_t *len) {
  if (!port) {
    g_error = "no port";
    return -1;
  }
  if (port->pending.empty()) {
    uint8_t buf[256];
    const long r = port->serial->read(buf, sizeof(buf), timeout_ms);
    if (r < 0) {
      g_error = "read failed (was the cable unplugged?)";
      return -1;
    }
    std::vector<sixeyes::Frame> frames;
    port->parser.feed(buf, static_cast<size_t>(r), frames);
    for (auto &f : frames) port->pending.push_back(std::move(f));
  }
  if (port->pending.empty()) return 0;
  sixeyes::Frame f = std::move(port->pending.front());
  port->pending.pop_front();
  if (f.payload.size() > cap) {
    g_error = "payload larger than the buffer";
    return -2;
  }
  *type = f.type;
  *seq = f.seq;
  *len = f.payload.size();
  if (!f.payload.empty()) std::memcpy(payload, f.payload.data(), f.payload.size());
  return 1;
}

const char *sixeyes_last_error(void) { return g_error.c_str(); }

}  // extern "C"
