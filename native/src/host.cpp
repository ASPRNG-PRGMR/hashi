#include "hashi/host.hpp"

#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstring>
#include <thread>

namespace hashi::host {

namespace {

double monotonic_now() {
  using clock = std::chrono::steady_clock;
  const auto since = clock::now().time_since_epoch();
  return std::chrono::duration<double>(since).count();
}

}  // namespace

// --- UnixSocket ------------------------------------------------------------

UnixSocket::~UnixSocket() { close(); }

UnixSocket& UnixSocket::operator=(UnixSocket&& other) noexcept {
  if (this != &other) {
    close();
    fd_ = other.fd_;
    other.fd_ = -1;
  }
  return *this;
}

void UnixSocket::close() {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

UnixSocket UnixSocket::connect(const std::string& path) {
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  if (path.size() >= sizeof address.sun_path) {
    throw HostError("socket path is too long: " + path);
  }
  std::memcpy(address.sun_path, path.c_str(), path.size() + 1);

  const int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd < 0) {
    throw HostError(std::string("creating a socket failed: ") +
                    std::strerror(errno));
  }
  UnixSocket result(fd);  // owns the fd from here, including on the throw below
  if (::connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof address) <
      0) {
    throw HostError("connecting to " + path + " failed: " +
                    std::strerror(errno) +
                    ". Is usbmuxd running and is the device attached?");
  }
  return result;
}

void UnixSocket::send_all(const Bytes& data) {
  if (fd_ < 0) throw HostError("socket is closed");
  std::size_t written = 0;
  while (written < data.size()) {
    const ssize_t count =
        ::send(fd_, data.data() + written, data.size() - written, MSG_NOSIGNAL);
    if (count < 0) {
      if (errno == EINTR) continue;
      throw HostError(std::string("send failed: ") + std::strerror(errno));
    }
    if (count == 0) throw HostError("the peer closed the connection on send");
    written += static_cast<std::size_t>(count);
  }
}

Bytes UnixSocket::recv_exactly(std::size_t count) {
  if (fd_ < 0) throw HostError("socket is closed");
  Bytes out(count);
  std::size_t read = 0;
  while (read < count) {
    const ssize_t got = ::recv(fd_, out.data() + read, count - read, 0);
    if (got < 0) {
      if (errno == EINTR) continue;
      throw HostError(std::string("recv failed: ") + std::strerror(errno));
    }
    if (got == 0) {
      throw HostError("the peer closed the connection after " +
                      std::to_string(read) + " of " + std::to_string(count) +
                      " bytes");
    }
    read += static_cast<std::size_t>(got);
  }
  return out;
}

Bytes UnixSocket::recv_available(std::size_t limit) {
  if (fd_ < 0) throw HostError("socket is closed");
  pollfd descriptor{fd_, POLLIN, 0};
  const int ready = ::poll(&descriptor, 1, 0);
  if (ready < 0) {
    if (errno == EINTR) return {};
    throw HostError(std::string("poll failed: ") + std::strerror(errno));
  }
  if (ready == 0) return {};

  Bytes out(limit);
  const ssize_t got = ::recv(fd_, out.data(), limit, MSG_DONTWAIT);
  if (got < 0) {
    if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) return {};
    throw HostError(std::string("recv failed: ") + std::strerror(errno));
  }
  // Zero from a readable socket means the peer closed, which the caller sees
  // as an empty read; run() stops when the next send fails.
  out.resize(static_cast<std::size_t>(got));
  return out;
}

// --- Pacer -----------------------------------------------------------------

Pacer::Pacer(int fps, std::function<double()> now)
    : interval_s_(static_cast<double>(stream::frame_interval_ms(fps)) / 1000.0),
      now_(now ? std::move(now) : std::function<double()>(monotonic_now)) {}

double Pacer::sleep_s() {
  const double now = now_();
  if (!scheduled_) {
    next_ = now + interval_s_;
    scheduled_ = true;
    return 0.0;
  }
  const double wait = next_ - now;
  if (wait <= 0.0) {
    // Later than the target: reset rather than try to catch up in a burst.
    next_ = now + interval_s_;
    return 0.0;
  }
  next_ += interval_s_;
  return wait;
}

double Pacer::wait() {
  const double delay = sleep_s();
  if (delay > 0.0) {
    std::this_thread::sleep_for(std::chrono::duration<double>(delay));
  }
  return delay;
}

// --- FrameGate -------------------------------------------------------------

FrameGate::FrameGate(bool skip_unchanged, double keepalive_interval_s,
                     std::function<double()> now)
    : skip_unchanged_(skip_unchanged),
      keepalive_interval_s_(keepalive_interval_s),
      now_(now ? std::move(now) : std::function<double()>(monotonic_now)) {}

bool FrameGate::should_send(const Bytes& payload) {
  if (!skip_unchanged_ || !have_last_) return true;
  if (payload != last_sent_) return true;
  return now_() - last_send_at_ >= keepalive_interval_s_;
}

void FrameGate::note_sent(const Bytes& payload) {
  last_sent_ = payload;
  have_last_ = true;
  last_send_at_ = now_();
}

// --- HostSession -----------------------------------------------------------

HostSession::HostSession(Options options)
    : options_(options),
      gate_(options.skip_unchanged, options.keepalive_interval_s) {
  if (options_.fps <= 0) {
    throw HostError("fps must be positive, got " + std::to_string(options_.fps));
  }
  if (options_.keepalive_interval_s <= 0.0) {
    throw HostError("the keepalive interval must be positive");
  }
}

Bytes HostSession::recv_usbmux_message() {
  // The 16-byte header carries the total length, including itself.
  const Bytes header = socket_.recv_exactly(usbmux::kHeaderLen);
  const usbmux::Header fields =
      usbmux::decode_header(header.data(), header.size());
  if (fields.length < usbmux::kHeaderLen) {
    throw HostError("usbmux message claims " + std::to_string(fields.length) +
                    " bytes, which is shorter than its own header");
  }
  Bytes message = header;
  const std::size_t remaining = fields.length - usbmux::kHeaderLen;
  if (remaining > 0) {
    const Bytes body = socket_.recv_exactly(remaining);
    append(message, body);
  }
  return message;
}

startup::Dimensions HostSession::connect() {
  if (connected_) throw HostError("already connected");

  socket_ = UnixSocket::connect(options_.usbmux_socket);

  // Discover the device id rather than assume it. usbmuxd assigns a fresh
  // DeviceID on every attach, so a hard-coded one is right for a single
  // session and wrong for the next -- met live as a BADDEV failure after a
  // reconnect.
  if (options_.device_id < 0) {
    socket_.send_all(usbmux::build_list_devices());
    const auto listing = usbmux::decode_message(recv_usbmux_message());
    devices_seen_ = usbmux::parse_device_list(listing.second);
    options_.device_id =
        usbmux::select_device(devices_seen_, usbmux::kIpadProductId);
    // ListDevices is answered on its own connection; Connect needs a fresh
    // one, since a successful Connect turns the socket into the device's byte
    // stream.
    socket_.close();
    socket_ = UnixSocket::connect(options_.usbmux_socket);
  }

  socket_.send_all(usbmux::build_connect(options_.device_id));
  const auto reply = usbmux::decode_message(recv_usbmux_message());
  if (!usbmux::result_is_success(reply.second)) {
    const std::string name = usbmux::result_name(reply.second);
    std::string hint;
    if (name == "BADDEV") {
      hint =
          " usbmuxd does not know this device id. It is reassigned on every "
          "attach, so this usually means the device detached and came back.";
    } else if (name == "CONNREFUSED") {
      hint =
          " Nothing is listening on the application port - the Splashtop app "
          "is not running or not in the foreground.";
    }
    throw HostError("usbmux Connect to device " +
                    std::to_string(options_.device_id) + " failed: " + name +
                    " (Number=" +
                    std::to_string(usbmux::parse_result(reply.second)) + ")." +
                    hint);
  }

  // The byte-order probe, then HELLO / READY / the extra-data request.
  const std::vector<Bytes> sequence = startup::host_startup_sequence();
  if (sequence.size() != 4) {
    throw HostError("the startup sequence is not four records");
  }
  socket_.send_all(sequence[0]);
  if (!startup::probe_reply_accepted(socket_.recv_exactly(4))) {
    throw HostError("the device rejected the byte-order probe");
  }

  socket_.send_all(sequence[1]);
  const startup::Dimensions dimensions =
      startup::parse_hello_ack(socket_.recv_exactly(16));

  socket_.send_all(sequence[2]);
  startup::parse_ready_ack(socket_.recv_exactly(16));

  socket_.send_all(sequence[3]);
  const Bytes header = socket_.recv_exactly(4);
  const Bytes body = socket_.recv_exactly(
      startup::extra_data_length(header.data(), header.size()));
  diff_jpeg_ = startup::diff_jpeg_enabled(body);
  if (diff_jpeg_) {
    throw HostError(
        "the device enabled diff_jpeg, which this host cannot produce: the "
        "differential path is gated but was never observed, so nothing is "
        "known about what it transmits. Refusing to guess.");
  }

  connected_ = true;
  return dimensions;
}

void HostSession::drain_inbound(capture::FrameSource& source,
                                gnome::VirtualDisplaySession* display) {
  const Bytes data = socket_.recv_available();
  if (data.empty()) return;
  for (const stream::TlvRecord& record :
       demuxer_.feed(data.data(), data.size())) {
    ++stats_.records_received;
    apply(record, source, display);
  }
}

void HostSession::apply(const stream::TlvRecord& record,
                        capture::FrameSource& source,
                        gnome::VirtualDisplaySession* display) {
  // Only type 7 carries input -- the only type ever observed inbound, and the
  // only one the decode byte-swaps. Anything else is counted and dropped
  // rather than interpreted, because nothing establishes what it means.
  if (record.tlv_type != stream::kTlvType7) {
    ++stats_.records_ignored;
    return;
  }
  if (!options_.inject || display == nullptr) {
    ++stats_.records_ignored;
    return;
  }

  // Absolute motion is dropped until the PipeWire stream has a consumer, and
  // Mutter reports success anyway, so this cannot be detected from the D-Bus
  // reply. Having captured a frame is the proof that a consumer exists.
  if (!display->stream_consumed()) {
    if (source.pipewire_frames_captured() > 0) {
      display->set_stream_consumed(true);
    } else {
      ++stats_.records_dropped_no_consumer;
      return;
    }
  }

  // field1 and field2 are the coordinates: monitor-relative pixels in the
  // display's own 1280x960 space, passed straight through.
  const auto calls = display->inject(static_cast<int>(record.field0),
                                     static_cast<int>(record.field1),
                                     static_cast<int>(record.field2));
  if (!calls.empty()) {
    ++stats_.events_injected;
  } else {
    ++stats_.records_ignored;
  }
}

SessionStats HostSession::run(capture::FrameSource& source,
                              std::uint64_t frames,
                              gnome::VirtualDisplaySession* display,
                              std::function<bool()> should_stop) {
  if (!connected_) throw HostError("not connected; call connect() first");

  Pacer pacer(options_.fps);
  std::uint64_t ticks = 0;
  while ((frames == 0 || ticks < frames) &&
         !(should_stop && should_stop())) {
    const Bytes payload = source.next_payload();

    if (gate_.should_send(payload)) {
      const Bytes record = stream::encode_image_record(payload);
      socket_.send_all(record);
      gate_.note_sent(payload);
      ++stats_.frames_sent;
      stats_.bytes_sent += record.size();
    } else {
      ++stats_.frames_skipped;
    }
    ++ticks;

    drain_inbound(source, display);
    pacer.wait();
  }
  return stats_;
}

}  // namespace hashi::host
