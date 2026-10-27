// A USB serial (CDC) port. Windows and POSIX (Linux, macOS) implementations are in serial.cpp.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace sixeyes {

class SerialPort {
 public:
  virtual ~SerialPort() = default;
  // Opens e.g. "COM3" or "/dev/ttyACM0". On failure returns nullptr and fills `error`.
  static std::unique_ptr<SerialPort> open(const std::string &name, std::string &error);
  // Returns the number of bytes written, or -1 on error.
  virtual long write(const uint8_t *data, size_t n) = 0;
  // Waits up to timeout_ms for data. Returns bytes read (0 = timeout), or -1 on error.
  virtual long read(uint8_t *buf, size_t cap, int timeout_ms) = 0;
};

}  // namespace sixeyes
