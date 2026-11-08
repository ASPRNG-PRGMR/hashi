// The composed host: transport, pacing, and the loop that ties every layer
// together.
//
// **Never executed.** Each layer beneath this is validated -- the protocol
// against the capture, the arguments and frames against the Python reference by
// conformance -- but the composition is not, for this implementation. The
// Python one is what ran in FED-HOST-E001.
//
// connect() contacts the iPad and run() drives a Mutter session, so neither
// should be called without the user's explicit say-so.
#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "hashi/bytes.hpp"
#include "hashi/capture.hpp"
#include "hashi/session.hpp"
#include "hashi/startup.hpp"
#include "hashi/stream.hpp"
#include "hashi/usbmux.hpp"

namespace hashi::host {

constexpr int kTargetFps = capture::kTargetFps;

class HostError : public std::runtime_error {
 public:
  explicit HostError(const std::string& what) : std::runtime_error(what) {}
};

/// An owned AF_UNIX stream socket.
///
/// The only I/O in the native tree. Everything below the socket is byte
/// manipulation, which is why the rest of the port could be checked offline.
class UnixSocket {
 public:
  UnixSocket() = default;
  explicit UnixSocket(int fd) : fd_(fd) {}
  ~UnixSocket();

  UnixSocket(const UnixSocket&) = delete;
  UnixSocket& operator=(const UnixSocket&) = delete;
  UnixSocket(UnixSocket&& other) noexcept : fd_(other.fd_) { other.fd_ = -1; }
  UnixSocket& operator=(UnixSocket&& other) noexcept;

  /// Connect to a Unix socket path. Throws HostError on failure.
  static UnixSocket connect(const std::string& path);

  bool is_open() const { return fd_ >= 0; }
  void close();

  /// Write every byte, retrying a short write.
  void send_all(const Bytes& data);
  /// Read exactly ``count`` bytes, or throw if the peer closes first.
  Bytes recv_exactly(std::size_t count);
  /// Read whatever has already arrived, without blocking. May be empty.
  Bytes recv_available(std::size_t limit = 65536);

 private:
  int fd_ = -1;
};

/// Paces the outbound frame loop to a target rate.
///
/// **A deliberate divergence from the agent, stated as such.** The decoded
/// pacing reads only GetSystemTime's wMilliseconds, so its own elapsed
/// measurement wraps every second and cannot tell a 1.2-second stall from a
/// 200 ms one. hashi_stream's pacing_sleep_ms reproduces that faithfully,
/// including the wrap; a host has no reason to inherit it, so this uses a
/// monotonic clock. frame_interval_ms still supplies the target, so the
/// interval and its truncation are the decoded ones.
class Pacer {
 public:
  /// ``now`` returns seconds from any fixed origin; injectable for tests and
  /// for the conformance comparison against the reference's Pacer.
  explicit Pacer(int fps = kTargetFps, std::function<double()> now = {});

  /// Seconds to wait before the next frame. Never negative.
  ///
  /// Schedules against the previous *target* rather than the previous wakeup,
  /// so a late frame does not push every later frame late. A stall longer than
  /// one interval resets the schedule instead of catching up in a burst.
  double sleep_s();

  /// sleep_s(), then actually sleep. Returns the delay taken.
  double wait();

  double interval_s() const { return interval_s_; }

 private:
  double interval_s_;
  std::function<double()> now_;
  double next_ = 0.0;
  bool scheduled_ = false;
};

/// Decides whether a frame is worth putting on the wire.
///
/// **Why this exists.** Measured 2026-11-08: a frame is ~372 KB and the encode
/// costs 4.9 ms against a 33 ms budget, so the host is nowhere near CPU-bound
/// -- it is bound by ~11 MB/s of USB for frames that are usually identical. A
/// static desktop sent 999 byte-identical copies of one frame in 38 seconds.
///
/// **The keepalive, and why transmission does not simply stop.** What the
/// device does when a stream goes quiet has never been observed; the captured
/// Windows session streamed continuously for its whole life, so there is no
/// evidence either way about a timeout. Rather than guess, an unchanged frame
/// is still re-sent, just at keepalive_interval_s instead of every tick -- at
/// the default, 1 fps instead of 30, roughly a 97% saving with no behaviour
/// the device has not already seen.
class FrameGate {
 public:
  explicit FrameGate(bool skip_unchanged = true,
                     double keepalive_interval_s = 1.0,
                     std::function<double()> now = {});

  /// Whether to send, given the frame about to go out.
  bool should_send(const Bytes& payload);
  /// Record that a frame was actually sent.
  void note_sent(const Bytes& payload);

 private:
  bool skip_unchanged_;
  double keepalive_interval_s_;
  std::function<double()> now_;
  Bytes last_sent_;
  bool have_last_ = false;
  double last_send_at_ = 0.0;
};

struct SessionStats {
  std::uint64_t frames_sent = 0;
  std::uint64_t bytes_sent = 0;
  std::uint64_t records_received = 0;
  std::uint64_t events_injected = 0;
  std::uint64_t records_ignored = 0;
  /// Records discarded because the PipeWire stream had no consumer yet, so
  /// injecting would have been a silent no-op for motion.
  std::uint64_t records_dropped_no_consumer = 0;
  /// Frames not transmitted because they were byte-identical to the last one
  /// sent and the keepalive was not yet due.
  std::uint64_t frames_skipped = 0;
};

/// The whole host: usbmux transport, the decoded handshake, the frame loop and
/// input injection.
class HostSession {
 public:
  struct Options {
    /// Negative means "discover it from usbmuxd", which is what a host should
    /// do: the daemon reassigns DeviceID on every attach.
    std::int64_t device_id = -1;
    int fps = kTargetFps;
    bool inject = true;
    bool skip_unchanged = true;
    double keepalive_interval_s = 1.0;
    std::string usbmux_socket = usbmux::kLinuxSocket;
  };

  explicit HostSession(Options options);

  /// Open the usbmux socket and complete the decoded handshake.
  ///
  /// **This contacts the iPad.** Every step is the validated one from
  /// FED-START-E001; the only thing new is that it is driven from here.
  /// Returns the client dimensions the device reports.
  startup::Dimensions connect();

  /// Stream frames and apply inbound input until ``frames`` have been sent.
  ///
  /// ``frames`` of 0 runs until ``should_stop`` returns true or the socket
  /// fails. Inbound records are drained each iteration rather than on a
  /// thread: the observed rate is modest (1,449 records in 45 seconds) and one
  /// loop is far easier to reason about than two.
  ///
  /// ``should_stop`` is a predicate rather than a flag pointer so a caller can
  /// drive it from a signal handler, which may only touch a sig_atomic_t.
  SessionStats run(capture::FrameSource& source, std::uint64_t frames = 0,
                   gnome::VirtualDisplaySession* display = nullptr,
                   std::function<bool()> should_stop = {});

  const SessionStats& stats() const { return stats_; }
  std::int64_t device_id() const { return options_.device_id; }
  const std::vector<usbmux::Device>& devices_seen() const {
    return devices_seen_;
  }
  bool diff_jpeg() const { return diff_jpeg_; }

 private:
  void drain_inbound(capture::FrameSource& source,
                     gnome::VirtualDisplaySession* display);
  void apply(const stream::TlvRecord& record, capture::FrameSource& source,
             gnome::VirtualDisplaySession* display);
  Bytes recv_usbmux_message();

  Options options_;
  UnixSocket socket_;
  stream::InboundDemuxer demuxer_;
  FrameGate gate_;
  SessionStats stats_;
  std::vector<usbmux::Device> devices_seen_;
  bool diff_jpeg_ = false;
  bool connected_ = false;
};

}  // namespace hashi::host
