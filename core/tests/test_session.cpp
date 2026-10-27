// Tests the C++ session against a scripted fake arm (no hardware, no serial port).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "sixeyes/codec.hpp"
#include "sixeyes/session.hpp"
#include "sixeyes/stream.hpp"
#include "sixeyes_protocol.h"

using namespace sixeyes;

static int g_failures = 0;
#define CHECK(cond)                                               \
  do {                                                            \
    if (!(cond)) {                                                \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
      g_failures++;                                               \
    }                                                             \
  } while (0)

static bool contains(const std::string &text, const char *part) { return text.find(part) != std::string::npos; }

// Plays the arm's side of the protocol, just enough for the session's rules.
class FakeArm : public ByteStream {
 public:
  // What the fake does, set by a test before it connects:
  uint16_t protocol_version = SIXEYES_PROTOCOL_VERSION;
  uint8_t targets_status = SIXEYES_STATUS_OK;
  bool silent = false;  // never answers anything

  // What the fake saw:
  std::atomic<int> heartbeats{0};
  std::atomic<int> targets_received{0};
  std::atomic<int> homes_received{0};

  // The state it reports:
  uint8_t homing_state = SIXEYES_HOMING_STATE_UNHOMED;
  uint8_t control_source = SIXEYES_CONTROL_SOURCE_BLE;
  float measured[SIXEYES_JOINT_COUNT] = {};

  long write(const uint8_t *data, size_t n) override {
    std::lock_guard<std::mutex> lock(m_);
    std::vector<Frame> frames;
    parser_.feed(data, n, frames);
    for (const Frame &f : frames) onFrame(f);
    return static_cast<long>(n);
  }

  long read(uint8_t *buf, size_t cap, int timeout_ms) override {
    std::unique_lock<std::mutex> lock(m_);
    cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&] { return !out_.empty(); });
    const size_t k = std::min(cap, out_.size());
    for (size_t i = 0; i < k; i++) {
      buf[i] = out_.front();
      out_.pop_front();
    }
    return static_cast<long>(k);
  }

  void pushState() {
    std::lock_guard<std::mutex> lock(m_);
    queueState();
  }

 private:
  void queue(uint8_t type, const uint8_t *payload, size_t n) {
    const std::vector<uint8_t> bytes = encode_frame(type, ++out_seq_, payload, n);
    out_.insert(out_.end(), bytes.begin(), bytes.end());
    cv_.notify_all();
  }

  void queueAck(const Frame &f, uint8_t status) {
    sixeyes_ack_t a = {f.type, f.seq, status};
    uint8_t p[SIXEYES_SIZE_ACK];
    sixeyes_ack_pack(&a, p);
    queue(SIXEYES_MSG_ACK, p, sizeof(p));
  }

  void queueState() {
    sixeyes_state_t st = {};
    st.t_ms = ++t_ms_;
    st.homing_state = homing_state;
    st.control_source = control_source;
    std::memcpy(st.measured, measured, sizeof(measured));
    uint8_t p[SIXEYES_SIZE_STATE];
    sixeyes_state_pack(&st, p);
    queue(SIXEYES_MSG_STATE, p, sizeof(p));
  }

  void onFrame(const Frame &f) {
    if (silent) return;
    switch (f.type) {
      case SIXEYES_MSG_HELLO: {
        sixeyes_hello_ack_t h = {};
        h.protocol_version = protocol_version;
        h.fw_major = 0;
        h.fw_minor = 1;
        h.fw_patch = 0;
        h.capabilities = SIXEYES_CAP_HOMING | SIXEYES_CAP_ECHO_TARGETS;
        uint8_t p[SIXEYES_SIZE_HELLO_ACK];
        sixeyes_hello_ack_pack(&h, p);
        queue(SIXEYES_MSG_HELLO_ACK, p, sizeof(p));
        const bool ok = protocol_version == SIXEYES_PROTOCOL_VERSION;
        queueAck(f, ok ? SIXEYES_STATUS_OK : SIXEYES_STATUS_BAD_VERSION);
        if (ok) queueState();  // the stream starts after a good hello
        break;
      }
      case SIXEYES_MSG_HEARTBEAT: heartbeats++; queueAck(f, SIXEYES_STATUS_OK); break;
      case SIXEYES_MSG_TARGETS: targets_received++; queueAck(f, targets_status); break;
      case SIXEYES_MSG_SET_CONTROL_SOURCE: control_source = SIXEYES_CONTROL_SOURCE_USB; queueAck(f, SIXEYES_STATUS_OK); queueState(); break;
      case SIXEYES_MSG_HOME: homes_received++; homing_state = SIXEYES_HOMING_STATE_READY; queueAck(f, SIXEYES_STATUS_OK); queueState(); break;
      default: queueAck(f, SIXEYES_STATUS_OK); break;
    }
  }

  std::mutex m_;
  std::condition_variable cv_;
  std::deque<uint8_t> out_;
  FrameParser parser_;
  uint8_t out_seq_ = 0;
  uint32_t t_ms_ = 0;
};

// A session over a fake arm that the test can still reach.
struct Rig {
  FakeArm *arm;
  std::unique_ptr<Session> session;
  explicit Rig(std::unique_ptr<FakeArm> fake, int ack_timeout_ms = 300)
      : arm(fake.get()), session(new Session(std::move(fake), ack_timeout_ms, 20)) {}
};

static void sleepMs(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

static void testConnect() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  const ArmInfo info = r.session->info();
  CHECK(info.protocol_version == SIXEYES_PROTOCOL_VERSION);
  CHECK(info.fw_major == 0 && info.fw_minor == 1 && info.fw_patch == 0);
  CHECK((info.capabilities & SIXEYES_CAP_ECHO_TARGETS) != 0);
  ArmState st;
  CHECK(r.session->state(st));
  CHECK(st.homing_state == SIXEYES_HOMING_STATE_UNHOMED);
  CHECK(r.session->stateAgeSeconds() < 1.0);
}

static void testVersionMismatchIsExplained() {
  auto fake = std::make_unique<FakeArm>();
  fake->protocol_version = 99;
  Rig r(std::move(fake));
  const std::string err = r.session->connect();
  CHECK(contains(err, "mismatch"));
  CHECK(contains(err, "Update this software"));  // the arm is newer than us
}

static void testSilentArmTimesOut() {
  auto fake = std::make_unique<FakeArm>();
  fake->silent = true;
  Rig r(std::move(fake), 100);
  CHECK(contains(r.session->connect(), "did not answer"));
}

static void testCommandsAndPlainRefusals() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  CHECK(r.session->setControlUsb().empty());
  CHECK(r.session->home().empty());
  CHECK(r.session->waitReady(1000).empty());
  ArmState st;
  CHECK(r.session->state(st) && st.homing_state == SIXEYES_HOMING_STATE_READY && st.control_source == SIXEYES_CONTROL_SOURCE_USB);

  const float goal[SIXEYES_JOINT_COUNT] = {0.1f, 0.2f, 0.3f, 0.4f, 0.5f, 60.0f};
  CHECK(r.session->sendTargets(goal).empty());
  CHECK(r.arm->targets_received == 1);

  r.arm->targets_status = SIXEYES_STATUS_NOT_HOMED;
  CHECK(contains(r.session->sendTargets(goal), "not homed"));
  r.arm->targets_status = SIXEYES_STATUS_BUSY;
  CHECK(contains(r.session->sendTargets(goal), "busy"));
}

static void testStreamedTargetsReportRefusalsLater() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  r.arm->targets_status = SIXEYES_STATUS_FAULTED;
  const float goal[SIXEYES_JOINT_COUNT] = {};
  r.session->sendTargetsNoWait(goal);
  sleepMs(100);
  CHECK(r.arm->targets_received == 1);
  CHECK(contains(r.session->takeRefusal(), "fault"));
  CHECK(r.session->takeRefusal().empty());  // reading clears it
}

static void testStateIsParsed() {
  auto fake = std::make_unique<FakeArm>();
  fake->measured[0] = 0.5f;
  fake->measured[5] = 40.0f;
  Rig r(std::move(fake));
  CHECK(r.session->connect().empty());
  ArmState st;
  CHECK(r.session->state(st));
  CHECK(st.measured[0] == 0.5f && st.measured[5] == 40.0f);
}

static void testHeartbeatKeepsTheArmAlive() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  CHECK(r.arm->heartbeats == 0);  // not homed and not in control: nothing to keep alive
  CHECK(r.session->setControlUsb().empty());
  CHECK(r.session->home().empty());
  CHECK(r.session->waitReady(1000).empty());
  // 20 ms period. Wait for the beats to arrive instead of counting them in a fixed time: a busy CI machine
  // (the macOS runner) can be slow, and what matters here is that the beats keep coming.
  for (int i = 0; i < 1500 && r.arm->heartbeats < 5; ++i) sleepMs(2);
  CHECK(r.arm->heartbeats >= 5);
}

static void testWaitReadyTimesOut() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  CHECK(contains(r.session->waitReady(100), "Timed out"));
}

static void testStateAgeGrowsWhenTheArmGoesQuiet() {
  Rig r(std::make_unique<FakeArm>());
  CHECK(r.session->connect().empty());
  sleepMs(150);
  CHECK(r.session->stateAgeSeconds() > 0.1);
  r.arm->pushState();
  // Poll: a busy CI machine can delay the reader thread, and the age is only small just after a state arrives.
  bool fresh = false;
  for (int i = 0; i < 500 && !fresh; ++i) {
    sleepMs(2);
    fresh = r.session->stateAgeSeconds() < 0.1;
  }
  CHECK(fresh);
}

int main() {
  testConnect();
  testVersionMismatchIsExplained();
  testSilentArmTimesOut();
  testCommandsAndPlainRefusals();
  testStreamedTargetsReportRefusalsLater();
  testStateIsParsed();
  testHeartbeatKeepsTheArmAlive();
  testWaitReadyTimesOut();
  testStateAgeGrowsWhenTheArmGoesQuiet();
  if (g_failures) {
    std::printf("%d check(s) failed\n", g_failures);
    return 1;
  }
  std::printf("all C++ session checks passed\n");
  return 0;
}
