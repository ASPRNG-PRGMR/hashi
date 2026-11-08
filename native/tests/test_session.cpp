// Tests for the live Mutter session layer that touch no bus.
//
// Building a GVariant and validating options are pure operations, so they can
// be asserted here. Everything that would create a session, make a D-Bus call
// or put a monitor on the user's desktop is deliberately absent: that is the
// first live run of this implementation, and it has not happened.
//
// The GVariant payloads are also diffed against PyGObject's by
// native/tools/conformance.py, which is the stronger check -- these cover the
// shape and the refusals.
#include "testing.hpp"

#include <gio/gio.h>

#include <string>

#include "hashi/session.hpp"

using namespace hashi;

namespace {

std::string type_of(::GVariant* floating) {
  glib::Variant owned(floating);
  return g_variant_get_type_string(owned.get());
}

/// The type string of one entry's value, which is what a signature mistake
/// would change.
std::string child_type(const gnome::PropDict& properties, const char* key) {
  glib::Variant dict(gnome::to_variant_dict(properties));
  glib::Variant value(g_variant_lookup_value(dict.get(), key, nullptr));
  if (!value) return "<missing>";
  return g_variant_get_type_string(value.get());
}

}  // namespace

TEST("session: a property dictionary builds an a{sv}") {
  CHECK_EQ(type_of(gnome::to_variant_dict(gnome::record_virtual_properties())),
           std::string("a{sv}"));
  CHECK_EQ(type_of(gnome::to_variant_dict(
               gnome::screen_cast_session_properties())),
           std::string("a{sv}"));
}

TEST("session: the signatures Mutter requires are the ones that land") {
  const auto properties = gnome::record_virtual_properties();
  // A uint32 cursor mode sent as an int32 is the quiet port bug this guards.
  CHECK_EQ(child_type(properties, "cursor-mode"), std::string("u"));
  CHECK_EQ(child_type(properties, "modes"), std::string("aa{sv}"));
  CHECK_EQ(child_type(gnome::virtual_monitor_mode(), "size"),
           std::string("(uu)"));
  CHECK_EQ(child_type(gnome::virtual_monitor_mode(), "refresh-rate"),
           std::string("d"));
  CHECK_EQ(child_type(gnome::virtual_monitor_mode(), "is-preferred"),
           std::string("b"));
  CHECK_EQ(child_type(gnome::screen_cast_session_properties("17"),
                      "remote-desktop-session-id"),
           std::string("s"));
}

TEST("session: an omitted key is absent rather than defaulted") {
  CHECK_EQ(child_type(gnome::record_virtual_properties(), "is-platform"),
           std::string("<missing>"));
  CHECK_EQ(child_type(gnome::virtual_monitor_mode(1280, 960, 0.0),
                      "refresh-rate"),
           std::string("<missing>"));
  CHECK_EQ(child_type(gnome::screen_cast_session_properties(),
                      "remote-desktop-session-id"),
           std::string("<missing>"));
}

TEST("session: construction validates without touching the bus") {
  // Inert by design: a bad size or cursor mode is reported before anything
  // appears on the user's desktop.
  gnome::VirtualDisplaySession::Options bad_cursor;
  bad_cursor.cursor_mode = 3;
  CHECK_THROWS(gnome::VirtualDisplaySession(bad_cursor));

  gnome::VirtualDisplaySession::Options bad_size;
  bad_size.width = 0;
  CHECK_THROWS(gnome::VirtualDisplaySession(bad_size));
}

TEST("session: a fresh session is closed and has nothing to report") {
  gnome::VirtualDisplaySession session;
  CHECK(!session.is_open());
  CHECK(!session.stream_consumed());
  CHECK_EQ(session.node_id(), std::uint32_t{0});
  CHECK(session.stream_path().empty());
  CHECK(session.session_id().empty());
}

TEST("session: closing a session that never opened reports no error") {
  // Teardown must not mask the failure that caused it. Stopping a session that
  // was never started fails with "Session not started", so an early failure in
  // open() would otherwise surface as that instead of its real cause. With no
  // session object there is nothing to stop and nothing to report.
  gnome::VirtualDisplaySession session;
  CHECK(session.close().empty());
  CHECK(!session.is_open());
}

TEST("session: injecting before open is refused") {
  gnome::VirtualDisplaySession session;
  CHECK_THROWS(session.inject(10, 100, 100));
  // And the consumer gate is a separate refusal from the missing session, so
  // setting it does not make an unopened session injectable.
  session.set_stream_consumed(true);
  CHECK_THROWS(session.inject(10, 100, 100));
}

TEST("session: reading stream parameters before open is refused") {
  gnome::VirtualDisplaySession session;
  CHECK_THROWS(session.stream_parameters());
}

int main() { return ::testing::run_all(); }
