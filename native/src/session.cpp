#include "hashi/session.hpp"

#include <string>

namespace hashi::gnome {

namespace {

/// One entry of an a{sv}, as a floating GVariant.
::GVariant* value_variant(const PropValue& value) {
  switch (value.kind()) {
    case PropValue::Kind::Bool:
      return g_variant_new_boolean(value.as_bool() ? TRUE : FALSE);
    case PropValue::Kind::UInt32:
      return g_variant_new_uint32(value.as_uint32());
    case PropValue::Kind::Int32:
      return g_variant_new_int32(value.as_int32());
    case PropValue::Kind::Double:
      return g_variant_new_double(value.as_double());
    case PropValue::Kind::String:
      return g_variant_new_string(value.as_string().c_str());
    case PropValue::Kind::Size:
      return g_variant_new("(uu)", value.as_size().first,
                           value.as_size().second);
    case PropValue::Kind::DictList: {
      GVariantBuilder builder;
      g_variant_builder_init(&builder, G_VARIANT_TYPE("aa{sv}"));
      for (const PropDict& dict : value.as_dict_list()) {
        g_variant_builder_add_value(&builder, to_variant_dict(dict));
      }
      return g_variant_builder_end(&builder);
    }
  }
  throw GnomeError("unreachable: unknown PropValue kind");
}

}  // namespace

::GVariant* to_variant_dict(const PropDict& properties) {
  GVariantBuilder builder;
  g_variant_builder_init(&builder, G_VARIANT_TYPE("a{sv}"));
  for (const auto& entry : properties) {
    g_variant_builder_add(&builder, "{sv}", entry.first.c_str(),
                          value_variant(entry.second));
  }
  return g_variant_builder_end(&builder);
}

VirtualDisplaySession::VirtualDisplaySession()
    : VirtualDisplaySession(Options()) {}

VirtualDisplaySession::VirtualDisplaySession(Options options)
    : options_(options) {
  // Construction stays inert: validating the arguments now means a bad size or
  // cursor mode is reported before anything appears on the user's desktop.
  (void)record_virtual_properties(
      {virtual_monitor_mode(options_.width, options_.height,
                            options_.refresh_rate)},
      options_.cursor_mode, options_.is_platform);
}

VirtualDisplaySession::~VirtualDisplaySession() {
  // A dangling virtual monitor would outlive the process, so teardown happens
  // even on an exception path. close() swallows its own errors by design.
  if (started_ || remote_desktop_session_ || screen_cast_session_) {
    close();
  }
}

glib::Object<GDBusProxy> VirtualDisplaySession::proxy(const char* bus_name,
                                                      const char* object_path,
                                                      const char* interface) {
  if (!bus_) {
    glib::ErrorSink error;
    bus_.reset(g_bus_get_sync(G_BUS_TYPE_SESSION, nullptr, error.out()));
    error.check("connecting to the session bus");
    if (!bus_) throw GnomeError("no session bus connection");
  }
  glib::ErrorSink error;
  glib::Object<GDBusProxy> result(g_dbus_proxy_new_sync(
      bus_.get(), G_DBUS_PROXY_FLAGS_NONE, nullptr, bus_name, object_path,
      interface, nullptr, error.out()));
  error.check(std::string("creating a proxy for ") + interface);
  if (!result) {
    throw GnomeError(std::string("no proxy for ") + interface);
  }
  return result;
}

int VirtualDisplaySession::version_of(GDBusProxy* proxy) {
  glib::Variant value(g_dbus_proxy_get_cached_property(proxy, "Version"));
  if (!value) {
    throw GnomeError(
        "no Version property on the interface - this does not look like the "
        "Mutter API FED-DBUS-E001 verified");
  }
  return static_cast<int>(g_variant_get_uint32(value.get()));
}

namespace {

struct StreamWait {
  std::uint32_t node_id = 0;
  bool have_node_id = false;
  glib::MainLoop* loop = nullptr;
};

void on_stream_signal(GDBusProxy* /*proxy*/, const char* /*sender*/,
                      const char* signal, GVariant* parameters,
                      gpointer user_data) {
  auto* wait = static_cast<StreamWait*>(user_data);
  if (signal == nullptr || std::string(signal) != "PipeWireStreamAdded") return;
  std::uint32_t node_id = 0;
  g_variant_get(parameters, "(u)", &node_id);
  wait->node_id = node_id;
  wait->have_node_id = true;
  if (wait->loop != nullptr) wait->loop->quit();
}

gboolean on_stream_timeout(gpointer user_data) {
  auto* wait = static_cast<StreamWait*>(user_data);
  if (wait->loop != nullptr) wait->loop->quit();
  return G_SOURCE_REMOVE;
}

/// Call a method taking no arguments and returning nothing of interest.
void call_void(GDBusProxy* proxy, const char* method,
               const std::string& context) {
  glib::ErrorSink error;
  glib::Variant reply(g_dbus_proxy_call_sync(proxy, method, nullptr,
                                             G_DBUS_CALL_FLAGS_NONE, -1,
                                             nullptr, error.out()));
  error.check(context);
}

/// Call a method and read the single object path it returns.
std::string call_for_path(GDBusProxy* proxy, const char* method,
                          ::GVariant* arguments, const std::string& context) {
  glib::ErrorSink error;
  glib::Variant reply(g_dbus_proxy_call_sync(proxy, method, arguments,
                                             G_DBUS_CALL_FLAGS_NONE, -1,
                                             nullptr, error.out()));
  error.check(context);
  if (!reply) throw GnomeError(context + ": empty reply");
  const char* path = nullptr;
  g_variant_get(reply.get(), "(&o)", &path);
  if (path == nullptr) throw GnomeError(context + ": no object path in reply");
  return std::string(path);
}

}  // namespace

std::uint32_t VirtualDisplaySession::open() {
  if (started_) throw GnomeError("the session is already open");

  glib::Object<GDBusProxy> remote_desktop = proxy(
      kRemoteDesktopBusName, kRemoteDesktopObjectPath, kRemoteDesktopIface);
  glib::Object<GDBusProxy> screen_cast =
      proxy(kScreenCastBusName, kScreenCastObjectPath, kScreenCastIface);

  if (options_.require_verified_versions) {
    check_versions(version_of(screen_cast.get()),
                   version_of(remote_desktop.get()));
  }

  {
    glib::Variant supported(g_dbus_proxy_get_cached_property(
        remote_desktop.get(), "SupportedDeviceTypes"));
    if (supported) {
      const int types = static_cast<int>(g_variant_get_uint32(supported.get()));
      if (!supports_device_types(types, kDeviceTypePointer)) {
        throw GnomeError("RemoteDesktop reports SupportedDeviceTypes=" +
                         std::to_string(types) +
                         ", which lacks pointer support");
      }
    }
  }

  // 1. The remote desktop session, and its id. CreateSession takes no
  //    arguments here -- only ScreenCast.CreateSession takes a properties
  //    dictionary.
  const std::string rd_path = call_for_path(
      remote_desktop.get(), "CreateSession", nullptr,
      "creating the remote desktop session");
  remote_desktop_session_ =
      proxy(kRemoteDesktopBusName, rd_path.c_str(), kRemoteDesktopSessionIface);
  {
    glib::Variant id(g_dbus_proxy_get_cached_property(
        remote_desktop_session_.get(), "SessionId"));
    if (!id) throw GnomeError("the remote desktop session exposed no SessionId");
    const char* text = g_variant_get_string(id.get(), nullptr);
    session_id_ = text != nullptr ? text : "";
  }

  // 2. The screen cast session, bound to it by id.
  //
  //    The reference carries a PyGObject-specific note here --
  //    GLib.Variant("(a{sv})", prebuilt) raises KeyError, so it uses
  //    new_tuple. That is a binding artefact with no C equivalent; the tuple
  //    wrapping below is the ordinary way and the workaround must not be
  //    "ported".
  ::GVariant* sc_children[1] = {
      to_variant_dict(screen_cast_session_properties(session_id_))};
  const std::string sc_path =
      call_for_path(screen_cast.get(), "CreateSession",
                    g_variant_new_tuple(sc_children, 1),
                    "creating the screen cast session");
  screen_cast_session_ =
      proxy(kScreenCastBusName, sc_path.c_str(), kScreenCastSessionIface);

  // 3. The pinned virtual monitor. With "modes" the stream is non-resizable,
  //    so negotiation cannot hand back a size the JPEG prelude cannot describe.
  const PropDict properties = record_virtual_properties(
      {virtual_monitor_mode(options_.width, options_.height,
                            options_.refresh_rate)},
      options_.cursor_mode, options_.is_platform);
  ::GVariant* rv_children[1] = {to_variant_dict(properties)};
  stream_path_ = call_for_path(screen_cast_session_.get(), "RecordVirtual",
                               g_variant_new_tuple(rv_children, 1),
                               "recording a virtual monitor");

  // 4. Subscribe before starting, so the node id cannot be missed.
  glib::Object<GDBusProxy> stream =
      proxy(kScreenCastBusName, stream_path_.c_str(), kScreenCastStreamIface);
  glib::MainLoop loop;
  StreamWait wait;
  wait.loop = &loop;
  const gulong handler =
      g_signal_connect(stream.get(), "g-signal",
                       G_CALLBACK(on_stream_signal), &wait);

  // 5. Starting the remote desktop session starts the cast with it.
  try {
    call_void(remote_desktop_session_.get(), "Start",
              "starting the remote desktop session");
    started_ = true;
    if (!wait.have_node_id) {
      const guint timeout = g_timeout_add_seconds(
          static_cast<guint>(options_.stream_timeout_seconds),
          on_stream_timeout, &wait);
      loop.run();
      // If the signal arrived first the timeout is still pending, and firing
      // later would quit a loop this function no longer owns.
      g_source_remove(timeout);
    }
  } catch (...) {
    g_signal_handler_disconnect(stream.get(), handler);
    throw;
  }
  g_signal_handler_disconnect(stream.get(), handler);

  if (!wait.have_node_id) {
    throw GnomeError(
        "no PipeWireStreamAdded signal arrived within " +
        std::to_string(options_.stream_timeout_seconds) +
        "s; the stream never started, so there is no node to capture from");
  }
  node_id_ = wait.node_id;
  have_node_id_ = true;
  return node_id_;
}

std::vector<std::string> VirtualDisplaySession::stream_parameters() {
  if (stream_path_.empty()) throw GnomeError("no stream; call open() first");
  glib::Object<GDBusProxy> stream =
      proxy(kScreenCastBusName, stream_path_.c_str(), kScreenCastStreamIface);
  glib::Variant value(
      g_dbus_proxy_get_cached_property(stream.get(), "Parameters"));
  std::vector<std::string> out;
  if (!value) return out;
  GVariantIter iter;
  g_variant_iter_init(&iter, value.get());
  const char* key = nullptr;
  GVariant* entry = nullptr;
  while (g_variant_iter_next(&iter, "{&sv}", &key, &entry)) {
    glib::Variant owned(entry);
    out.push_back(std::string(key != nullptr ? key : "") + "=" +
                  g_variant_get_type_string(owned.get()));
  }
  return out;
}

std::vector<InjectionCall> VirtualDisplaySession::inject(int field0, int x,
                                                         int y) {
  if (!remote_desktop_session_ || stream_path_.empty()) {
    throw GnomeError("no session; call open() first");
  }
  if (!stream_consumed_) {
    throw GnomeError(
        "refusing to inject: nothing is consuming the PipeWire stream yet, so "
        "Mutter would silently drop every absolute motion while still "
        "reporting success. Buttons would still land, at a stale pointer "
        "position - which looks like selected text and misbehaving windows "
        "rather than an error. Start the capture and pull at least one frame, "
        "then set stream_consumed.");
  }

  const std::vector<InjectionCall> calls = plan_injection(
      field0, x, y, stream_path_, options_.width, options_.height);
  for (const InjectionCall& call : calls) {
    ::GVariant* arguments = nullptr;
    if (call.method == "NotifyPointerMotionAbsolute") {
      arguments = g_variant_new("(sdd)", call.args.at(0).as_string().c_str(),
                                call.args.at(1).as_double(),
                                call.args.at(2).as_double());
    } else if (call.method == "NotifyPointerButton") {
      arguments = g_variant_new("(ib)", call.args.at(0).as_int32(),
                                call.args.at(1).as_bool() ? TRUE : FALSE);
    } else {
      throw GnomeError("no signature known for " + call.method);
    }
    glib::ErrorSink error;
    glib::Variant reply(g_dbus_proxy_call_sync(
        remote_desktop_session_.get(), call.method.c_str(), arguments,
        G_DBUS_CALL_FLAGS_NONE, -1, nullptr, error.out()));
    error.check(call.method);
  }
  return calls;
}

std::vector<std::string> VirtualDisplaySession::close() {
  std::vector<std::string> errors;

  // Stopping the remote desktop session stops the cast with it and destroys
  // the screen cast session object, so the cast is only stopped directly if
  // that did not happen or failed. Observed: stopping both in sequence makes
  // the second call fail with "Object does not exist at path ...".
  bool stopped = false;
  if (remote_desktop_session_) {
    glib::ErrorSink error;
    glib::Variant reply(g_dbus_proxy_call_sync(
        remote_desktop_session_.get(), "Stop", nullptr,
        G_DBUS_CALL_FLAGS_NONE, -1, nullptr, error.out()));
    if (error.failed()) {
      errors.push_back("RemoteDesktop.Stop: " + error.message());
    } else {
      stopped = true;
    }
  }
  if (!stopped && screen_cast_session_) {
    glib::ErrorSink error;
    glib::Variant reply(g_dbus_proxy_call_sync(
        screen_cast_session_.get(), "Stop", nullptr, G_DBUS_CALL_FLAGS_NONE,
        -1, nullptr, error.out()));
    if (error.failed()) {
      errors.push_back("ScreenCast.Stop: " + error.message());
    }
  }

  // Cleared either way, so a dangling virtual monitor cannot survive a
  // partially opened session.
  remote_desktop_session_.reset();
  screen_cast_session_.reset();
  started_ = false;
  stream_consumed_ = false;
  stream_path_.clear();
  node_id_ = 0;
  have_node_id_ = false;
  return errors;
}

}  // namespace hashi::gnome
