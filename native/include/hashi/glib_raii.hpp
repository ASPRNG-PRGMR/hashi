// Minimal owning wrappers for the GLib types this port touches.
//
// The C++17 choice was made for exactly this: the live layers juggle a bus
// connection, two sessions, a stream proxy, a main loop and a GError on every
// call, and the faults the first live run produced were teardown-ordering
// ones. Nothing below is clever -- each type owns one reference and releases it
// once -- but it means no path through the session code can leak a proxy or
// drop a GError on the floor.
#pragma once

#include <gio/gio.h>
#include <glib.h>

#include <stdexcept>
#include <string>
#include <utility>

namespace hashi::glib {

/// Raised when a GLib or D-Bus call fails. Carries GError's message.
class GError_ : public std::runtime_error {
 public:
  explicit GError_(const std::string& what) : std::runtime_error(what) {}
};

/// Owns a GError* and turns it into an exception on demand.
///
/// Every g_* call that can fail takes a GError**; forgetting to free one is
/// the usual leak in GLib C code, so the pointer never leaves this class.
class ErrorSink {
 public:
  ErrorSink() = default;
  ~ErrorSink() { if (error_ != nullptr) g_error_free(error_); }
  ErrorSink(const ErrorSink&) = delete;
  ErrorSink& operator=(const ErrorSink&) = delete;

  ::GError** out() { return &error_; }
  bool failed() const { return error_ != nullptr; }

  /// Throw if the call failed, prefixing ``context``.
  void check(const std::string& context) {
    if (error_ == nullptr) return;
    const std::string message = context + ": " +
                                (error_->message != nullptr ? error_->message
                                                            : "unknown error");
    g_error_free(error_);
    error_ = nullptr;
    throw GError_(message);
  }

  /// The message, for a caller that wants to record rather than throw.
  std::string message() const {
    if (error_ == nullptr) return {};
    return error_->message != nullptr ? error_->message : "unknown error";
  }

  void clear() {
    if (error_ != nullptr) {
      g_error_free(error_);
      error_ = nullptr;
    }
  }

 private:
  ::GError* error_ = nullptr;
};

/// Owns one GObject reference.
template <typename T>
class Object {
 public:
  Object() = default;
  explicit Object(T* owned) : ptr_(owned) {}
  ~Object() { reset(); }

  Object(const Object&) = delete;
  Object& operator=(const Object&) = delete;
  Object(Object&& other) noexcept : ptr_(other.ptr_) { other.ptr_ = nullptr; }
  Object& operator=(Object&& other) noexcept {
    if (this != &other) {
      reset();
      ptr_ = other.ptr_;
      other.ptr_ = nullptr;
    }
    return *this;
  }

  T* get() const { return ptr_; }
  explicit operator bool() const { return ptr_ != nullptr; }

  void reset(T* owned = nullptr) {
    if (ptr_ != nullptr) g_object_unref(ptr_);
    ptr_ = owned;
  }

 private:
  T* ptr_ = nullptr;
};

/// Owns one GVariant reference, sinking a floating one.
class Variant {
 public:
  Variant() = default;
  /// Takes ownership. A floating variant is sunk, so the caller need not care
  /// which kind GLib handed back.
  explicit Variant(::GVariant* owned)
      : ptr_(owned != nullptr ? g_variant_ref_sink(owned) : nullptr) {}
  ~Variant() { if (ptr_ != nullptr) g_variant_unref(ptr_); }

  Variant(const Variant&) = delete;
  Variant& operator=(const Variant&) = delete;
  Variant(Variant&& other) noexcept : ptr_(other.ptr_) { other.ptr_ = nullptr; }
  Variant& operator=(Variant&& other) noexcept {
    if (this != &other) {
      if (ptr_ != nullptr) g_variant_unref(ptr_);
      ptr_ = other.ptr_;
      other.ptr_ = nullptr;
    }
    return *this;
  }

  ::GVariant* get() const { return ptr_; }
  explicit operator bool() const { return ptr_ != nullptr; }

 private:
  ::GVariant* ptr_ = nullptr;
};

/// Owns a GMainLoop.
class MainLoop {
 public:
  MainLoop() : loop_(g_main_loop_new(nullptr, FALSE)) {}
  ~MainLoop() { if (loop_ != nullptr) g_main_loop_unref(loop_); }
  MainLoop(const MainLoop&) = delete;
  MainLoop& operator=(const MainLoop&) = delete;

  ::GMainLoop* get() const { return loop_; }
  void run() { g_main_loop_run(loop_); }
  void quit() { g_main_loop_quit(loop_); }

 private:
  ::GMainLoop* loop_ = nullptr;
};

}  // namespace hashi::glib
