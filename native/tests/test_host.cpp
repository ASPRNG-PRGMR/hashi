// Tests for the composed host that need neither the device nor a compositor.
//
// The pacer and the frame gate are pure given an injected clock. The socket is
// exercised over a socketpair, which is real I/O against a loopback peer
// rather than a mock -- so send_all, recv_exactly and recv_available are
// tested as written, without usbmuxd and without the iPad.
#include "testing.hpp"

#include <sys/socket.h>

#include <string>
#include <vector>

#include "hashi/host.hpp"

using namespace hashi;

namespace {

/// A clock that returns a scripted sequence, then holds its last value.
class ScriptedClock {
 public:
  explicit ScriptedClock(std::vector<double> values)
      : values_(std::move(values)) {}
  double operator()() {
    if (index_ < values_.size()) return values_[index_++];
    return values_.empty() ? 0.0 : values_.back();
  }

 private:
  std::vector<double> values_;
  std::size_t index_ = 0;
};

/// A connected pair of Unix sockets, for exercising the transport.
struct SocketPair {
  host::UnixSocket a;
  host::UnixSocket b;

  SocketPair() {
    int fds[2] = {-1, -1};
    if (::socketpair(AF_UNIX, SOCK_STREAM, 0, fds) != 0) {
      throw ::testing::Failure("socketpair failed");
    }
    a = host::UnixSocket(fds[0]);
    b = host::UnixSocket(fds[1]);
  }
};

}  // namespace

// ---------------------------------------------------------------------------
// Pacer
// ---------------------------------------------------------------------------

TEST("pacer: the interval is the decoded one, truncated") {
  // frame_interval_ms(30) is 33, not 33.33: the truncation is the agent's.
  host::Pacer pacer(30, ScriptedClock({0.0}));
  CHECK_EQ(pacer.interval_s(), 0.033);
  host::Pacer sixty(60, ScriptedClock({0.0}));
  CHECK_EQ(sixty.interval_s(), 0.016);
}

TEST("pacer: the first tick does not wait") {
  host::Pacer pacer(30, ScriptedClock({100.0}));
  CHECK_EQ(pacer.sleep_s(), 0.0);
}

TEST("pacer: it schedules against the target, not the wakeup") {
  // Woken 10 ms late, the next wait is shortened so the schedule holds rather
  // than every later frame inheriting the lateness.
  host::Pacer pacer(30, ScriptedClock({0.0, 0.010, 0.033}));
  CHECK_EQ(pacer.sleep_s(), 0.0);        // schedules the target at 0.033
  const double second = pacer.sleep_s();  // now 0.010, so 0.023 to wait
  CHECK(second > 0.022 && second < 0.024);
}

TEST("pacer: a stall longer than an interval resets instead of bursting") {
  // Clock jumps a full second past the target: catching up would mean a burst
  // of 30 frames, so the schedule restarts from now.
  host::Pacer pacer(30, ScriptedClock({0.0, 1.0, 1.0}));
  CHECK_EQ(pacer.sleep_s(), 0.0);
  CHECK_EQ(pacer.sleep_s(), 0.0);
}

TEST("pacer: a wait is never negative") {
  host::Pacer pacer(30, ScriptedClock({0.0, 5.0, 10.0, 20.0}));
  for (int i = 0; i < 4; ++i) CHECK(pacer.sleep_s() >= 0.0);
}

// ---------------------------------------------------------------------------
// FrameGate
// ---------------------------------------------------------------------------

TEST("gate: the first frame always goes out") {
  host::FrameGate gate(true, 1.0, ScriptedClock({0.0}));
  CHECK(gate.should_send(Bytes{1, 2, 3}));
}

TEST("gate: an identical frame is suppressed until the keepalive is due") {
  // Times: note_sent at 0, then asked at 0.1 (not due) and at 1.5 (due).
  host::FrameGate gate(true, 1.0, ScriptedClock({0.0, 0.1, 1.5}));
  const Bytes frame{1, 2, 3};
  gate.note_sent(frame);
  CHECK(!gate.should_send(frame));
  CHECK(gate.should_send(frame));
}

TEST("gate: a changed frame goes out immediately") {
  host::FrameGate gate(true, 1.0, ScriptedClock({0.0, 0.001}));
  gate.note_sent(Bytes{1, 2, 3});
  CHECK(gate.should_send(Bytes{1, 2, 4}));
}

TEST("gate: a frame of the same length but different bytes is not identical") {
  // Comparing lengths alone would suppress a real change of equal size, which
  // on a display is a whole frame of content silently dropped.
  host::FrameGate gate(true, 1.0, ScriptedClock({0.0, 0.001}));
  gate.note_sent(Bytes{9, 9, 9, 9});
  CHECK(gate.should_send(Bytes{9, 9, 9, 8}));
}

TEST("gate: skipping can be turned off entirely") {
  host::FrameGate gate(false, 1.0, ScriptedClock({0.0, 0.0, 0.0}));
  const Bytes frame{1, 2, 3};
  gate.note_sent(frame);
  CHECK(gate.should_send(frame));
}

// ---------------------------------------------------------------------------
// UnixSocket
// ---------------------------------------------------------------------------

TEST("socket: bytes round-trip over a real socket pair") {
  SocketPair pair;
  const Bytes payload{0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x11};
  pair.a.send_all(payload);
  CHECK_EQ(pair.b.recv_exactly(payload.size()), payload);
}

TEST("socket: recv_exactly waits for the whole count across two writes") {
  SocketPair pair;
  pair.a.send_all(Bytes{1, 2, 3});
  pair.a.send_all(Bytes{4, 5});
  CHECK_EQ(pair.b.recv_exactly(5), (Bytes{1, 2, 3, 4, 5}));
}

TEST("socket: recv_available returns nothing rather than blocking") {
  SocketPair pair;
  CHECK(pair.b.recv_available().empty());
  pair.a.send_all(Bytes{7});
  CHECK_EQ(pair.b.recv_available(), (Bytes{7}));
}

TEST("socket: a peer that closes early is reported, not waited on forever") {
  SocketPair pair;
  pair.a.send_all(Bytes{1, 2});
  pair.a.close();
  // Two bytes are there; the third never arrives because the peer is gone.
  CHECK_THROWS(pair.b.recv_exactly(3));
}

TEST("socket: operations on a closed socket are refused") {
  host::UnixSocket socket;
  CHECK(!socket.is_open());
  CHECK_THROWS(socket.send_all(Bytes{1}));
  CHECK_THROWS(socket.recv_exactly(1));
  CHECK_THROWS(socket.recv_available());
  socket.close();  // harmless
}

TEST("socket: moving transfers the descriptor exactly once") {
  SocketPair pair;
  host::UnixSocket moved(std::move(pair.a));
  CHECK(moved.is_open());
  CHECK(!pair.a.is_open());
  moved.send_all(Bytes{42});
  CHECK_EQ(pair.b.recv_exactly(1), (Bytes{42}));
}

TEST("socket: connecting to a path with no listener fails with a hint") {
  CHECK_THROWS(host::UnixSocket::connect("/nonexistent/hashi-test-socket"));
  // A path longer than sun_path must be refused rather than truncated.
  CHECK_THROWS(host::UnixSocket::connect(std::string(200, 'x')));
}

// ---------------------------------------------------------------------------
// HostSession
// ---------------------------------------------------------------------------

TEST("host: impossible options are refused at construction") {
  host::HostSession::Options bad_fps;
  bad_fps.fps = 0;
  CHECK_THROWS(host::HostSession(bad_fps));

  host::HostSession::Options bad_keepalive;
  bad_keepalive.keepalive_interval_s = 0.0;
  CHECK_THROWS(host::HostSession(bad_keepalive));
}

TEST("host: running before connecting is refused") {
  host::HostSession session(host::HostSession::Options{});
  capture::SolidColourSource source(0, 0, 0, 16, 16);
  CHECK_THROWS(session.run(source, 1));
}

TEST("host: a fresh session has discovered nothing") {
  host::HostSession session(host::HostSession::Options{});
  // Negative means "discover it from usbmuxd", which is what a host should do:
  // the daemon reassigns DeviceID on every attach.
  CHECK(session.device_id() < 0);
  CHECK(session.devices_seen().empty());
  CHECK(!session.diff_jpeg());
  CHECK_EQ(session.stats().frames_sent, std::uint64_t{0});
}

TEST("host: a source that does not read PipeWire never proves a consumer") {
  // This is the guard that stops absolute motion being injected into a stream
  // nothing is consuming, where Mutter discards it and still reports success.
  capture::SolidColourSource solid(0, 0, 0, 16, 16);
  CHECK_EQ(solid.pipewire_frames_captured(), std::uint64_t{0});

  capture::PipeWireFrameSource::Options options;
  options.node_id = 1;
  capture::PipeWireFrameSource pipewire(options);
  CHECK_EQ(pipewire.pipewire_frames_captured(), std::uint64_t{0});
}

int main() { return ::testing::run_all(); }
