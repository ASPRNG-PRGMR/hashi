#include "hashi/gnome.hpp"

#include <algorithm>
#include <cstdio>
#include <map>
#include <sstream>

namespace hashi::gnome {

// --- PropValue -------------------------------------------------------------

PropValue PropValue::boolean(bool value) {
  PropValue out;
  out.kind_ = Kind::Bool;
  out.bool_ = value;
  return out;
}

PropValue PropValue::uint32(std::uint32_t value) {
  PropValue out;
  out.kind_ = Kind::UInt32;
  out.uint_ = value;
  return out;
}

PropValue PropValue::int32(std::int32_t value) {
  PropValue out;
  out.kind_ = Kind::Int32;
  out.int_ = value;
  return out;
}

PropValue PropValue::real(double value) {
  PropValue out;
  out.kind_ = Kind::Double;
  out.double_ = value;
  return out;
}

PropValue PropValue::string(std::string value) {
  PropValue out;
  out.kind_ = Kind::String;
  out.string_ = std::move(value);
  return out;
}

PropValue PropValue::size(std::uint32_t width, std::uint32_t height) {
  PropValue out;
  out.kind_ = Kind::Size;
  out.size_ = {width, height};
  return out;
}

PropValue PropValue::dict_list(std::vector<PropDict> value) {
  PropValue out;
  out.kind_ = Kind::DictList;
  out.dicts_ = std::move(value);
  return out;
}

std::string PropValue::signature() const {
  switch (kind_) {
    case Kind::Bool: return "b";
    case Kind::UInt32: return "u";
    case Kind::Int32: return "i";
    case Kind::Double: return "d";
    case Kind::String: return "s";
    case Kind::Size: return "(uu)";
    case Kind::DictList: return "aa{sv}";
  }
  throw GnomeError("unreachable: unknown PropValue kind");
}

namespace {

void require(bool condition, const char* what) {
  if (!condition) throw GnomeError(std::string("PropValue is not ") + what);
}

}  // namespace

bool PropValue::as_bool() const {
  require(kind_ == Kind::Bool, "a boolean");
  return bool_;
}

std::uint32_t PropValue::as_uint32() const {
  require(kind_ == Kind::UInt32, "a uint32");
  return uint_;
}

std::int32_t PropValue::as_int32() const {
  require(kind_ == Kind::Int32, "an int32");
  return int_;
}

double PropValue::as_double() const {
  require(kind_ == Kind::Double, "a double");
  return double_;
}

const std::string& PropValue::as_string() const {
  require(kind_ == Kind::String, "a string");
  return string_;
}

std::pair<std::uint32_t, std::uint32_t> PropValue::as_size() const {
  require(kind_ == Kind::Size, "a size");
  return size_;
}

const std::vector<PropDict>& PropValue::as_dict_list() const {
  require(kind_ == Kind::DictList, "a dictionary list");
  return dicts_;
}

// --- Canonical form --------------------------------------------------------
//
// A fixed textual rendering, so conformance.py can diff the D-Bus arguments
// the two implementations would send. Doubles use %.6f rather than a shortest
// representation: Python and C++ disagree about how to print a float, and that
// disagreement would otherwise look like a protocol difference.

std::string canonical(const PropValue& value) {
  std::ostringstream out;
  out << value.signature() << ':';
  switch (value.kind()) {
    case PropValue::Kind::Bool:
      out << (value.as_bool() ? "true" : "false");
      break;
    case PropValue::Kind::UInt32:
      out << value.as_uint32();
      break;
    case PropValue::Kind::Int32:
      out << value.as_int32();
      break;
    case PropValue::Kind::Double: {
      char buffer[64];
      std::snprintf(buffer, sizeof buffer, "%.6f", value.as_double());
      out << buffer;
      break;
    }
    case PropValue::Kind::String:
      out << '"' << value.as_string() << '"';
      break;
    case PropValue::Kind::Size:
      out << '(' << value.as_size().first << ',' << value.as_size().second
          << ')';
      break;
    case PropValue::Kind::DictList: {
      out << '[';
      bool first = true;
      for (const PropDict& dict : value.as_dict_list()) {
        if (!first) out << ',';
        first = false;
        out << canonical(dict);
      }
      out << ']';
      break;
    }
  }
  return out.str();
}

std::string canonical(const PropDict& dict) {
  // Sorted, so insertion order is not part of the comparison.
  std::map<std::string, std::string> sorted;
  for (const auto& entry : dict) {
    if (!sorted.emplace(entry.first, canonical(entry.second)).second) {
      throw GnomeError("duplicate key in dictionary: " + entry.first);
    }
  }
  std::ostringstream out;
  out << '{';
  bool first = true;
  for (const auto& entry : sorted) {
    if (!first) out << ',';
    first = false;
    out << entry.first << '=' << entry.second;
  }
  out << '}';
  return out.str();
}

std::string canonical(const InjectionCall& call) {
  std::ostringstream out;
  out << call.method << '(';
  bool first = true;
  for (const PropValue& arg : call.args) {
    if (!first) out << ',';
    first = false;
    out << canonical(arg);
  }
  out << ')';
  return out.str();
}

// --- Preconditions ---------------------------------------------------------

void check_versions(int screen_cast_version, int remote_desktop_version) {
  if (screen_cast_version != kVerifiedScreenCastVersion) {
    throw GnomeError(
        "ScreenCast API version " + std::to_string(screen_cast_version) +
        " was never verified; FED-DBUS-E001 checked version " +
        std::to_string(kVerifiedScreenCastVersion) +
        " on mutter-51.1. These are private APIs with no compatibility "
        "promise - re-verify the contracts before proceeding.");
  }
  if (remote_desktop_version != kVerifiedRemoteDesktopVersion) {
    throw GnomeError(
        "RemoteDesktop API version " + std::to_string(remote_desktop_version) +
        " was never verified; FED-DBUS-E001 checked version " +
        std::to_string(kVerifiedRemoteDesktopVersion) + " on mutter-51.1.");
  }
}

bool supports_device_types(int supported, int required) {
  return (supported & required) == required;
}

// --- Argument builders -----------------------------------------------------

PropDict virtual_monitor_mode(int width, int height, double refresh_rate,
                              bool is_preferred) {
  if (width <= 0 || height <= 0) {
    throw GnomeError("mode " + std::to_string(width) + "x" +
                     std::to_string(height) +
                     " has a non-positive dimension; Mutter rejects these as "
                     "'Invalid mode'");
  }
  PropDict mode;
  mode.emplace_back("size",
                    PropValue::size(static_cast<std::uint32_t>(width),
                                    static_cast<std::uint32_t>(height)));
  // A rate of zero omits the key, which makes Mutter default it to 60.0.
  if (refresh_rate != 0.0) {
    if (refresh_rate < 0.0) {
      throw GnomeError("refresh rate must be positive");
    }
    mode.emplace_back("refresh-rate", PropValue::real(refresh_rate));
  }
  mode.emplace_back("is-preferred", PropValue::boolean(is_preferred));
  return mode;
}

PropDict record_virtual_properties(const std::vector<PropDict>& modes,
                                   std::uint32_t cursor_mode,
                                   int is_platform) {
  if (cursor_mode != kCursorModeHidden && cursor_mode != kCursorModeEmbedded &&
      cursor_mode != kCursorModeMetadata) {
    throw GnomeError("unknown cursor mode " + std::to_string(cursor_mode) +
                     "; Mutter accepts 0, 1 or 2");
  }
  std::vector<PropDict> effective = modes;
  if (effective.empty()) effective.push_back(virtual_monitor_mode());

  // Mutter's create_mode_infos rejects both 'Multiple preferred modes' and
  // 'No preferred modes', so the count is checked here where the message can
  // name the caller's mistake.
  std::size_t preferred = 0;
  for (const PropDict& mode : effective) {
    for (const auto& entry : mode) {
      if (entry.first == "is-preferred" && entry.second.as_bool()) ++preferred;
    }
  }
  if (preferred != 1) {
    throw GnomeError("exactly one mode must be preferred, got " +
                     std::to_string(preferred) +
                     "; Mutter rejects 'Multiple preferred modes' and 'No "
                     "preferred modes'");
  }

  PropDict properties;
  properties.emplace_back("modes", PropValue::dict_list(effective));
  properties.emplace_back("cursor-mode", PropValue::uint32(cursor_mode));
  if (is_platform >= 0) {
    properties.emplace_back("is-platform",
                            PropValue::boolean(is_platform != 0));
  }
  return properties;
}

PropDict screen_cast_session_properties(
    const std::string& remote_desktop_session_id, int disable_animations) {
  PropDict properties;
  if (!remote_desktop_session_id.empty()) {
    properties.emplace_back("remote-desktop-session-id",
                            PropValue::string(remote_desktop_session_id));
  }
  if (disable_animations >= 0) {
    properties.emplace_back("disable-animations",
                            PropValue::boolean(disable_animations != 0));
  }
  return properties;
}

// --- Input injection -------------------------------------------------------
//
// 5 and 6 are left down and up: statically decoded from the
// MOUSEEVENTF_LEFTDOWN/LEFTUP constants the agent writes, and observed live in
// FED-LIVE-E001 (41 downs, 40 ups, strictly alternating).
//
// 8/9 (right) and 14/15 (middle) are static only. They come from the same six
// 7-byte stubs at RVA 0x40254-0x40277 and match the documented Win32
// right/middle constants exactly, so the mapping is sound -- but no such record
// has ever been seen on the wire, and the single-finger iPad input observed so
// far could not have produced one. Do not claim these work.

std::int32_t evdev_button_for_field0(int field0) {
  switch (field0) {
    case 5:
    case 6: return kBtnLeft;
    case 8:
    case 9: return kBtnRight;
    case 14:
    case 15: return kBtnMiddle;
    default: return 0;
  }
}

namespace {

/// Whether a button-carrying field0 presses rather than releases. Down and up
/// alternate within each pair, as observed for 5/6.
bool field0_pressed(int field0) {
  return field0 == 5 || field0 == 8 || field0 == 14;
}

}  // namespace

std::vector<InjectionCall> plan_injection(int field0, int x, int y,
                                          const std::string& stream_path,
                                          int width, int height) {
  if (stream_path.empty()) {
    throw GnomeError("stream_path is required; it is the 'stream' argument");
  }
  if (x < 0 || x > width || y < 0 || y > height) {
    throw GnomeError(
        "coordinate (" + std::to_string(x) + ", " + std::to_string(y) +
        ") is outside the " + std::to_string(width) + "x" +
        std::to_string(height) +
        " display; FED-LIVE-E001 observed every value inside it, so this is a "
        "decode or configuration fault rather than something to clamp");
  }

  const InjectionCall motion{
      "NotifyPointerMotionAbsolute",
      {PropValue::string(stream_path), PropValue::real(static_cast<double>(x)),
       PropValue::real(static_cast<double>(y))}};

  const std::int32_t button = evdev_button_for_field0(field0);
  if (button != 0) {
    return {motion,
            InjectionCall{"NotifyPointerButton",
                          {PropValue::int32(button),
                           PropValue::boolean(field0_pressed(field0))}}};
  }

  // field0 10 is motion (FED-LIVE-E001: 1,368 of 1,449 records). 4 and 7 are
  // the statically decoded movement-only values, which take the same mouse
  // path with no button stub; neither has been observed.
  if (field0 == 10 || field0 == 4 || field0 == 7) return {motion};

  return {};
}

}  // namespace hashi::gnome
