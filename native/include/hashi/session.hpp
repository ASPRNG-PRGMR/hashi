// The live Mutter session: creates a virtual monitor and injects input.
//
// **This has user-visible effects.** Opening a session makes a new monitor
// appear on the desktop and raises a screen-sharing indicator. Construction is
// inert; open() is the call that touches the bus.
//
// **Never executed.** Every signature used here is verified (FED-DBUS-E001)
// and the argument construction is checked against the Python reference by
// conformance, but the composition -- this ordering, and the claim that these
// calls add up to a working extended display -- is a design Inference that no
// run of *this* implementation has confirmed. The Python reference did confirm
// it (FED-HOST-E001), which is why the ordering below is copied from it rather
// than rederived. Treat the first execution as the experiment it is.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "hashi/glib_raii.hpp"
#include "hashi/gnome.hpp"

namespace hashi::gnome {

/// Build an a{sv} GVariant from a PropDict. Floating, as GLib callers expect.
::GVariant* to_variant_dict(const PropDict& properties);

/// Creates a Mutter virtual monitor and injects input into it.
class VirtualDisplaySession {
 public:
  struct Options {
    int width = kTargetWidth;
    int height = kTargetHeight;
    double refresh_rate = kTargetRefresh;
    std::uint32_t cursor_mode = kCursorModeEmbedded;
    /// -1 leaves the key unset, which is the default. See
    /// record_virtual_properties for why this is not decided here.
    int is_platform = -1;
    /// Refuse to drive a Mutter whose interface versions were never verified.
    bool require_verified_versions = true;
    /// How long to wait for PipeWireStreamAdded after Start.
    int stream_timeout_seconds = 10;
  };

  /// Two overloads rather than a defaulted parameter: GCC rejects `= {}` for
  /// this nested aggregate, and spelling the default out is clearer anyway.
  VirtualDisplaySession();
  explicit VirtualDisplaySession(Options options);
  ~VirtualDisplaySession();

  VirtualDisplaySession(const VirtualDisplaySession&) = delete;
  VirtualDisplaySession& operator=(const VirtualDisplaySession&) = delete;

  /// Create both sessions, pin the monitor and start the stream.
  ///
  /// Returns the PipeWire node id to hand to ``pipewiresrc path=``.
  ///
  /// The ordering is the one FED-DBUS-E001 derived: the remote-desktop session
  /// first, because the screen cast is bound to it by id and remote-desktop
  /// driven casts are started and stopped by the remote desktop session; and
  /// the PipeWireStreamAdded subscription before Start, so the node id cannot
  /// be missed.
  std::uint32_t open();

  /// Stop the session and release the virtual monitor.
  ///
  /// Returns the teardown errors it swallowed, if any. Teardown must never
  /// mask the failure that caused it: stopping a session that was never
  /// started fails with "Session not started", so an early failure in open()
  /// would otherwise surface as that instead of its real cause.
  std::vector<std::string> close();

  /// Read the stream's Parameters dictionary, as "key=type" entries.
  ///
  /// **Do not expect size or position here -- a virtual stream has neither.**
  /// The only key observed is mapping-id. set_stream_parameters has branches
  /// for monitor, area and window streams and none for virtual, and it runs in
  /// initable_init before the virtual monitor exists. Assert the geometry on
  /// the negotiated PipeWire caps instead.
  std::vector<std::string> stream_parameters();

  /// Apply one inbound input record. Returns the calls actually made.
  ///
  /// **A successful return does not prove delivery.** Mutter's
  /// transform_position returns FALSE until the stream has a ClutterStageView,
  /// and the handler then logs "Dropping early absolute pointer motion" and
  /// completes the call successfully anyway.
  std::vector<InjectionCall> inject(int field0, int x, int y);

  /// Whether something is actually consuming the PipeWire stream.
  ///
  /// Measured 2026-11-08: absolute motion is silently dropped until the stream
  /// has a consumer. With Mutter's idle timer as the probe, 40 motion calls
  /// with no consumer left idle climbing 14,741 -> 15,605 ms, and the same
  /// burst with a consumer attached took it 20,683 -> 21 ms. The D-Bus calls
  /// return success either way, so nothing in the reply distinguishes them.
  /// inject() refuses until this is set, because the alternative is clicks at
  /// a stale pointer position -- which looks like selected text and
  /// misbehaving windows rather than an error.
  void set_stream_consumed(bool consumed) { stream_consumed_ = consumed; }
  bool stream_consumed() const { return stream_consumed_; }

  const std::string& session_id() const { return session_id_; }
  const std::string& stream_path() const { return stream_path_; }
  std::uint32_t node_id() const { return node_id_; }
  bool is_open() const { return started_; }

 private:
  glib::Object<GDBusProxy> proxy(const char* bus_name, const char* object_path,
                                 const char* interface);
  static int version_of(GDBusProxy* proxy);

  Options options_;
  glib::Object<GDBusConnection> bus_;
  glib::Object<GDBusProxy> remote_desktop_session_;
  glib::Object<GDBusProxy> screen_cast_session_;
  bool started_ = false;
  bool stream_consumed_ = false;
  std::string session_id_;
  std::string stream_path_;
  std::uint32_t node_id_ = 0;
  bool have_node_id_ = false;
};

}  // namespace hashi::gnome
