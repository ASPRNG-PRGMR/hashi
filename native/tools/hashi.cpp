// The native host's entry point.
//
// Two of the three subcommands are inert. `plan` prints what a run would do
// and touches nothing; `devices` asks usbmuxd what is attached, which talks to
// the local daemon and not to the iPad. Only `run` streams frames, and it
// needs --allow-session because it has effects the user must choose: a monitor
// appears on the desktop, a screen-sharing indicator shows, and bytes go to
// the device.
//
// **`run` has never been executed.** Every layer under it is validated and the
// argument construction is checked against the Python reference, but this
// composition is not. The Python host is what ran in FED-HOST-E001. Treat the
// first run as the experiment it is.
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "hashi/host.hpp"

namespace {

volatile std::sig_atomic_t g_interrupted = 0;

void on_interrupt(int) { g_interrupted = 1; }

void usage() {
  std::printf(
      "hashi - a Linux host for the Splashtop Wired XDisplay iPad app\n"
      "\n"
      "usage: hashi <command> [options]\n"
      "\n"
      "commands:\n"
      "  plan      print what a run would do, and exit. Touches nothing.\n"
      "  devices   ask usbmuxd what is attached. Talks to the local daemon\n"
      "            only, not to the device.\n"
      "  run       stream frames and inject input. Requires --allow-session.\n"
      "\n"
      "options:\n"
      "  --fps N              frame rate (default 30)\n"
      "  --device-id N        skip discovery and use this usbmux device id.\n"
      "                       Discovery is normally right: usbmuxd reassigns\n"
      "                       the id on every attach.\n"
      "  --frames N           stop after N ticks (default: until interrupted)\n"
      "  --no-skip-unchanged  re-send every frame, even identical ones\n"
      "  --keepalive S        seconds between re-sends of an unchanged frame\n"
      "                       (default 1.0)\n"
      "  --solid              stream a solid black frame instead of capturing.\n"
      "                       Proves the wire path without a virtual monitor;\n"
      "                       input is not injected, because a source that\n"
      "                       does not consume the PipeWire stream cannot\n"
      "                       prove a consumer exists.\n"
      "  --allow-session      permit the effects described above\n");
}

struct Config {
  std::string command;
  int fps = hashi::host::kTargetFps;
  std::int64_t device_id = -1;
  std::uint64_t frames = 0;
  bool skip_unchanged = true;
  double keepalive_s = 1.0;
  bool solid = false;
  bool allow_session = false;
};

/// Returns false if the arguments do not parse; the message is already printed.
bool parse(int argc, char** argv, Config& config) {
  if (argc < 2) {
    usage();
    return false;
  }
  config.command = argv[1];
  for (int i = 2; i < argc; ++i) {
    const std::string flag = argv[i];
    auto next = [&](const char* name) -> const char* {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "hashi: %s needs a value\n", name);
        return nullptr;
      }
      return argv[++i];
    };
    if (flag == "--fps") {
      const char* value = next("--fps");
      if (value == nullptr) return false;
      config.fps = std::atoi(value);
    } else if (flag == "--device-id") {
      const char* value = next("--device-id");
      if (value == nullptr) return false;
      config.device_id = std::atoll(value);
    } else if (flag == "--frames") {
      const char* value = next("--frames");
      if (value == nullptr) return false;
      config.frames = std::strtoull(value, nullptr, 10);
    } else if (flag == "--keepalive") {
      const char* value = next("--keepalive");
      if (value == nullptr) return false;
      config.keepalive_s = std::atof(value);
    } else if (flag == "--no-skip-unchanged") {
      config.skip_unchanged = false;
    } else if (flag == "--solid") {
      config.solid = true;
    } else if (flag == "--allow-session") {
      config.allow_session = true;
    } else if (flag == "-h" || flag == "--help") {
      usage();
      return false;
    } else {
      std::fprintf(stderr, "hashi: unknown option %s\n", flag.c_str());
      return false;
    }
  }
  return true;
}

int command_plan(const Config& config) {
  std::printf("A run with this configuration would:\n");
  std::printf("  - connect to usbmuxd at %s\n", hashi::usbmux::kLinuxSocket);
  if (config.device_id < 0) {
    std::printf("  - discover the device id with ListDevices, selecting "
                "product id 0x%04x\n", hashi::usbmux::kIpadProductId);
  } else {
    std::printf("  - use device id %lld without discovery\n",
                static_cast<long long>(config.device_id));
  }
  std::printf("  - Connect to port %u, carried as %u byte-swapped\n",
              hashi::usbmux::kApplicationPort,
              hashi::usbmux::htons_port(hashi::usbmux::kApplicationPort));
  std::printf("  - complete the handshake: byte-order probe, HELLO, READY, "
              "extra-data request\n");
  if (config.solid) {
    std::printf("  - stream a solid black 1280x960 frame; no virtual monitor, "
                "and no injection\n");
  } else {
    std::printf("  - create a Mutter virtual monitor pinned to %dx%d at "
                "%.1f Hz, with an embedded cursor\n",
                hashi::gnome::kTargetWidth, hashi::gnome::kTargetHeight,
                hashi::gnome::kTargetRefresh);
    std::printf("  - capture it over PipeWire with:\n      %s\n",
                hashi::capture::pipeline_description(0).c_str());
    std::printf("  - inject inbound type-7 records as pointer events\n");
  }
  std::printf("  - pace to %d fps, an interval of %u ms\n", config.fps,
              hashi::stream::frame_interval_ms(config.fps));
  if (config.skip_unchanged) {
    std::printf("  - skip frames identical to the last one sent, but re-send "
                "one every %.1fs anyway, because what the device does with a "
                "silent stream has never been observed\n",
                config.keepalive_s);
  } else {
    std::printf("  - re-send every frame, identical or not\n");
  }
  if (config.frames != 0) {
    std::printf("  - stop after %llu ticks\n",
                static_cast<unsigned long long>(config.frames));
  }
  std::printf("\nNothing was done. Add --allow-session to `run` to do it.\n");
  return 0;
}

int command_devices(const Config&) {
  // Discovery only: this reaches usbmuxd, not the device.
  hashi::host::UnixSocket socket =
      hashi::host::UnixSocket::connect(hashi::usbmux::kLinuxSocket);
  socket.send_all(hashi::usbmux::build_list_devices());
  const hashi::Bytes header =
      socket.recv_exactly(hashi::usbmux::kHeaderLen);
  const hashi::usbmux::Header fields =
      hashi::usbmux::decode_header(header.data(), header.size());
  hashi::Bytes message = header;
  if (fields.length > hashi::usbmux::kHeaderLen) {
    const hashi::Bytes body =
        socket.recv_exactly(fields.length - hashi::usbmux::kHeaderLen);
    hashi::append(message, body);
  }
  const auto listing = hashi::usbmux::decode_message(message);
  const auto devices = hashi::usbmux::parse_device_list(listing.second);
  if (devices.empty()) {
    std::printf("usbmuxd reports no attached devices.\n");
    return 1;
  }
  for (const auto& device : devices) {
    std::printf("device id %lld  product 0x%04llx  %s  %s\n",
                static_cast<long long>(device.device_id),
                static_cast<unsigned long long>(device.product_id),
                device.connection_type.c_str(), device.serial.c_str());
  }
  return 0;
}

int command_run(const Config& config) {
  if (!config.allow_session) {
    std::fprintf(stderr,
                 "hashi: `run` needs --allow-session.\n"
                 "It sends bytes to the iPad%s. Use `hashi plan` to see "
                 "exactly what it would do.\n",
                 config.solid ? ""
                              : " and creates a Mutter session, which puts a "
                                "monitor on your desktop and raises a "
                                "screen-sharing indicator");
    return 2;
  }

  std::signal(SIGINT, on_interrupt);

  hashi::host::HostSession::Options options;
  options.fps = config.fps;
  options.device_id = config.device_id;
  options.skip_unchanged = config.skip_unchanged;
  options.keepalive_interval_s = config.keepalive_s;
  options.inject = !config.solid;
  hashi::host::HostSession session(options);

  std::unique_ptr<hashi::gnome::VirtualDisplaySession> display;
  std::unique_ptr<hashi::capture::FrameSource> source;

  if (config.solid) {
    source = std::make_unique<hashi::capture::SolidColourSource>();
  } else {
    display = std::make_unique<hashi::gnome::VirtualDisplaySession>();
    const std::uint32_t node_id = display->open();
    std::printf("virtual monitor up; PipeWire node %u\n", node_id);
    hashi::capture::PipeWireFrameSource::Options capture_options;
    capture_options.node_id = static_cast<int>(node_id);
    capture_options.fps = config.fps;
    auto pipewire =
        std::make_unique<hashi::capture::PipeWireFrameSource>(capture_options);
    pipewire->start();
    source = std::move(pipewire);
  }

  const hashi::startup::Dimensions dimensions = session.connect();
  std::printf("handshake complete; device reports %ux%u, diff_jpeg=%s\n",
              dimensions.width, dimensions.height,
              session.diff_jpeg() ? "true" : "false");

  // The handler may only touch a sig_atomic_t, so the loop reads it through a
  // predicate. Ctrl-C therefore ends the run at a tick boundary, which lets
  // the session and the virtual monitor tear down in order.
  hashi::host::SessionStats stats;
  try {
    stats = session.run(*source, config.frames, display.get(),
                        [] { return g_interrupted != 0; });
  } catch (const std::exception& error) {
    std::fprintf(stderr, "hashi: %s\n", error.what());
    stats = session.stats();
  }

  std::printf(
      "frames sent %llu (%llu skipped), %llu bytes; records received %llu, "
      "injected %llu, ignored %llu, dropped with no consumer %llu\n",
      static_cast<unsigned long long>(stats.frames_sent),
      static_cast<unsigned long long>(stats.frames_skipped),
      static_cast<unsigned long long>(stats.bytes_sent),
      static_cast<unsigned long long>(stats.records_received),
      static_cast<unsigned long long>(stats.events_injected),
      static_cast<unsigned long long>(stats.records_ignored),
      static_cast<unsigned long long>(stats.records_dropped_no_consumer));

  if (source) source->close();
  if (display) {
    for (const std::string& error : display->close()) {
      std::fprintf(stderr, "hashi: teardown: %s\n", error.c_str());
    }
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  Config config;
  if (!parse(argc, argv, config)) return 2;
  try {
    if (config.command == "plan") return command_plan(config);
    if (config.command == "devices") return command_devices(config);
    if (config.command == "run") return command_run(config);
  } catch (const std::exception& error) {
    std::fprintf(stderr, "hashi: %s\n", error.what());
    return 1;
  }
  std::fprintf(stderr, "hashi: unknown command %s\n", config.command.c_str());
  usage();
  return 2;
}
