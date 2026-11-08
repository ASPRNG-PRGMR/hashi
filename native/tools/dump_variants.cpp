// Emits the actual GVariant payloads as GLib's own text form.
//
// This goes a step beyond the canonical-form vectors. Those check that the two
// implementations decide on the same signatures and values; this checks that
// the decision survives contact with GLib -- that PropValue to GVariant lands
// the same payload PyGObject builds from the reference's
// {key: (signature, value)} mapping. Both sides print with g_variant_print, so
// a difference here is a real difference in the message that would go on the
// bus.
//
// It creates no session and makes no D-Bus call: building a variant touches
// nothing.
#include <gio/gio.h>

#include <cstdio>
#include <string>

#include "hashi/session.hpp"

using namespace hashi;

namespace {

void emit(const std::string& name, ::GVariant* floating) {
  glib::Variant owned(floating);
  char* text = g_variant_print(owned.get(), TRUE);
  std::printf("%s %s\n", name.c_str(), text);
  g_free(text);
}

}  // namespace

int main() {
  emit("variant_mode_default",
       gnome::to_variant_dict(gnome::virtual_monitor_mode()));
  emit("variant_mode_no_refresh",
       gnome::to_variant_dict(gnome::virtual_monitor_mode(1280, 960, 0.0)));
  emit("variant_record_virtual_default",
       gnome::to_variant_dict(gnome::record_virtual_properties()));
  emit("variant_record_virtual_platform_true",
       gnome::to_variant_dict(gnome::record_virtual_properties(
           {}, gnome::kCursorModeEmbedded, 1)));
  emit("variant_record_virtual_cursor_hidden",
       gnome::to_variant_dict(
           gnome::record_virtual_properties({}, gnome::kCursorModeHidden)));
  emit("variant_session_props_empty",
       gnome::to_variant_dict(gnome::screen_cast_session_properties()));
  emit("variant_session_props_id",
       gnome::to_variant_dict(gnome::screen_cast_session_properties("17")));
  emit("variant_session_props_both",
       gnome::to_variant_dict(gnome::screen_cast_session_properties("17", 1)));
  // Two modes, one preferred: exercises the aa{sv} nesting with more than one
  // entry, where an array-building mistake would show.
  {
    std::vector<gnome::PropDict> modes{
        gnome::virtual_monitor_mode(),
        gnome::virtual_monitor_mode(640, 480, 60.0, false)};
    emit("variant_record_virtual_two_modes",
         gnome::to_variant_dict(gnome::record_virtual_properties(modes)));
  }
  return 0;
}
