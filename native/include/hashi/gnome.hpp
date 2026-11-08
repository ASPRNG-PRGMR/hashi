// The Mutter contract layer: D-Bus argument construction and input mapping.
//
// Every signature and default here is the one verified three ways against
// mutter-51.1-1.fc45 in FED-DBUS-E001 -- live introspection, the
// GDBusMethodInfo tables inside libmutter-51.so.0, and the unpatched Fedora
// source RPM. Two of those results shape this file:
//
//   * RecordVirtual's "modes" key pins the virtual monitor to exactly
//     1280x960 and makes the PipeWire stream non-resizable. Without it the
//     monitor is created at whatever size the consumer negotiates. The JPEG
//     prelude hard-codes 1280x960, so a pinned mode turns a whole class of
//     size mismatch into an impossibility.
//   * NotifyPointerButton's button is an *evdev* code -- BTN_LEFT is 272, not
//     a Win32 MOUSEEVENTF_* flag. The XML does not say so; the implementation
//     does, via meta_evdev_button_to_clutter.
//
// This half builds arguments and plans calls as data. It links nothing: no
// GIO, no bus, no session. That is what lets native/tools/conformance.py check
// it against the Python reference offline, with no compositor running and no
// monitor appearing on the user's desk.
#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "hashi/bytes.hpp"

namespace hashi::gnome {

/// Raised when a value would be rejected by Mutter, or is outside what the
/// captures established.
class GnomeError : public std::runtime_error {
 public:
  explicit GnomeError(const std::string& what) : std::runtime_error(what) {}
};

// --- Target geometry -------------------------------------------------------

constexpr int kTargetWidth = 1280;
constexpr int kTargetHeight = 960;
constexpr double kTargetRefresh = 30.0;

// --- Bus names, paths and interfaces --------------------------------------

constexpr const char* kScreenCastBusName = "org.gnome.Mutter.ScreenCast";
constexpr const char* kScreenCastObjectPath = "/org/gnome/Mutter/ScreenCast";
constexpr const char* kScreenCastIface = "org.gnome.Mutter.ScreenCast";
constexpr const char* kScreenCastSessionIface =
    "org.gnome.Mutter.ScreenCast.Session";
constexpr const char* kScreenCastStreamIface =
    "org.gnome.Mutter.ScreenCast.Stream";

constexpr const char* kRemoteDesktopBusName = "org.gnome.Mutter.RemoteDesktop";
constexpr const char* kRemoteDesktopObjectPath =
    "/org/gnome/Mutter/RemoteDesktop";
constexpr const char* kRemoteDesktopIface = "org.gnome.Mutter.RemoteDesktop";
constexpr const char* kRemoteDesktopSessionIface =
    "org.gnome.Mutter.RemoteDesktop.Session";

/// The interface versions FED-DBUS-E001 verified against.
constexpr int kVerifiedScreenCastVersion = 4;
constexpr int kVerifiedRemoteDesktopVersion = 1;

// --- Enumerations from the verified XML ------------------------------------

constexpr std::uint32_t kCursorModeHidden = 0;
constexpr std::uint32_t kCursorModeEmbedded = 1;
constexpr std::uint32_t kCursorModeMetadata = 2;

constexpr int kDeviceTypeKeyboard = 1;
constexpr int kDeviceTypePointer = 2;
constexpr int kDeviceTypeTouchscreen = 4;

/// Published Linux UAPI values from <linux/input-event-codes.h>.
constexpr std::int32_t kBtnLeft = 0x110;    // 272
constexpr std::int32_t kBtnRight = 0x111;
constexpr std::int32_t kBtnMiddle = 0x112;

// --- A typed value, enough for the a{sv} dictionaries this protocol uses ---

class PropValue;
/// An ordered a{sv}. Order is preserved for readability; the canonical form
/// sorts, so two implementations need not agree on insertion order.
using PropDict = std::vector<std::pair<std::string, PropValue>>;

/// One D-Bus argument or dictionary entry, carrying its signature.
///
/// Signatures are part of the data rather than inferred from the C++ type: a
/// uint32 cursor mode and an int32 button code are different wire types, and
/// the whole point of this layer is to get those right.
class PropValue {
 public:
  enum class Kind { Bool, UInt32, Int32, Double, String, Size, DictList };

  static PropValue boolean(bool value);
  static PropValue uint32(std::uint32_t value);
  static PropValue int32(std::int32_t value);
  static PropValue real(double value);
  static PropValue string(std::string value);
  /// A "(uu)" width/height pair.
  static PropValue size(std::uint32_t width, std::uint32_t height);
  /// An "aa{sv}" array of dictionaries.
  static PropValue dict_list(std::vector<PropDict> value);

  Kind kind() const { return kind_; }
  /// The D-Bus signature this value carries.
  std::string signature() const;

  bool as_bool() const;
  std::uint32_t as_uint32() const;
  std::int32_t as_int32() const;
  double as_double() const;
  const std::string& as_string() const;
  std::pair<std::uint32_t, std::uint32_t> as_size() const;
  const std::vector<PropDict>& as_dict_list() const;

 private:
  Kind kind_ = Kind::Bool;
  bool bool_ = false;
  std::uint32_t uint_ = 0;
  std::int32_t int_ = 0;
  double double_ = 0.0;
  std::string string_;
  std::pair<std::uint32_t, std::uint32_t> size_{0, 0};
  std::vector<PropDict> dicts_;
};

/// A deterministic text form of a value or dictionary, for diffing against the
/// Python reference. Keys are sorted and doubles use a fixed format, so the
/// two implementations cannot differ merely in presentation.
std::string canonical(const PropValue& value);
std::string canonical(const PropDict& dict);

// --- Preconditions ---------------------------------------------------------

/// Refuse to drive a Mutter whose API versions were never verified.
///
/// These are private APIs with no compatibility promise, so a mismatch is a
/// reason to stop rather than to hope. A *higher* version is rejected too:
/// Mutter could have changed the "modes" contract, and this host would have no
/// way to notice except by producing wrong-sized frames.
void check_versions(int screen_cast_version, int remote_desktop_version);

/// Whether a SupportedDeviceTypes bitmask covers everything required.
bool supports_device_types(int supported, int required);

// --- Argument builders -----------------------------------------------------

/// One entry of RecordVirtual's "modes" array.
///
/// A refresh rate of 0 omits the key, which makes Mutter default it to 60.0.
PropDict virtual_monitor_mode(int width = kTargetWidth,
                              int height = kTargetHeight,
                              double refresh_rate = kTargetRefresh,
                              bool is_preferred = true);

/// The properties dictionary for Session.RecordVirtual.
///
/// Defaults to a single pinned 1280x960 at 30 Hz with an *embedded* cursor.
/// Embedded is the right default here, not Mutter's own default of hidden: the
/// protocol has no cursor channel, so compositing the cursor into the frames
/// is the only way the iPad can show one.
///
/// ``is_platform`` is a three-state choice -- -1 leaves the key out, which is
/// the default. Setting it true asks Mutter to treat the output as a real
/// monitor rather than a shared screen, but that also suppresses the sharing
/// indicator, so it stays an explicit decision for the user rather than one
/// this layer makes on their behalf.
PropDict record_virtual_properties(
    const std::vector<PropDict>& modes = {},
    std::uint32_t cursor_mode = kCursorModeEmbedded, int is_platform = -1);

/// The properties dictionary for ScreenCast.CreateSession.
///
/// The XML documents exactly two keys: remote-desktop-session-id (s) and
/// disable-animations (b). An empty id omits the former, and -1 omits the
/// latter.
PropDict screen_cast_session_properties(
    const std::string& remote_desktop_session_id = "",
    int disable_animations = -1);

// --- Input injection -------------------------------------------------------

/// One call to make on org.gnome.Mutter.RemoteDesktop.Session.
///
/// Kept as data rather than performed immediately, so a plan can be asserted
/// against the observed records with no session and no compositor.
struct InjectionCall {
  std::string method;
  std::vector<PropValue> args;
};

std::string canonical(const InjectionCall& call);

/// The evdev button code for a field0, or 0 if it carries no button.
std::int32_t evdev_button_for_field0(int field0);

/// Translate one inbound input record into RemoteDesktop calls.
///
/// x and y are monitor-relative pixels in the display's own 1280x960 space and
/// **pass straight through**: for a virtual stream the whole of
/// meta_stream_transform_position is a translation by the monitor's position in
/// the stage, with no scaling and no normalisation. The Windows agent's
/// 65535 virtual-desktop transform has no Linux equivalent to reproduce.
///
/// A button event is preceded by a motion call, because the iPad sends
/// coordinates with every record and a tap arrives as a bare 5 -> 6 with no
/// motion record before it. Pressing without moving first would land the press
/// wherever the pointer happened to be.
///
/// Returns an empty list for a field0 with no pointer meaning. Those values are
/// decoded but unexercised, and this host does not invent behaviour for them.
std::vector<InjectionCall> plan_injection(int field0, int x, int y,
                                          const std::string& stream_path,
                                          int width = kTargetWidth,
                                          int height = kTargetHeight);

}  // namespace hashi::gnome
