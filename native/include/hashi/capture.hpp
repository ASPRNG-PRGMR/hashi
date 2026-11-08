// PipeWire capture: a Mutter virtual monitor's buffers, as JPEG frame payloads.
//
// The geometry is pinned in two independent places, and deliberately so. The
// virtual monitor's mode fixes it on the compositor's side; the caps in the
// pipeline below fix it on the consumer's side. A mismatch therefore fails in
// negotiation rather than quietly producing frames of the wrong size, which
// matters because the 623-byte JPEG prelude hard-codes 1280x960 -- a frame of
// any other size would be a JPEG whose dimensions disagree with the stream the
// device was told to expect.
//
// The string builder and the geometry check are pure, so conformance compares
// them against the Python reference. Everything else needs a running
// compositor.
#pragma once

#include <cstdint>
#include <memory>
#include <string>

#include "hashi/bytes.hpp"
#include "hashi/encoder.hpp"

namespace hashi::capture {

constexpr int kTargetFps = 30;

/// Raised when capture cannot proceed.
class CaptureError : public std::runtime_error {
 public:
  explicit CaptureError(const std::string& what) : std::runtime_error(what) {}
};

/// The GStreamer pipeline that turns a PipeWire node into RGB frames.
///
/// ``node_id`` is what Stream.PipeWireStreamAdded hands back; it is the
/// ``path`` property of pipewiresrc.
///
/// videoconvert is unconditional: the compositor's buffers are typically BGRx
/// or BGRA. ``max-buffers=1 drop=true`` keeps the loop on the newest frame
/// rather than accumulating latency, which suits a display far more than
/// completeness would.
std::string pipeline_description(int node_id, int width = jpeg::kObservedWidth,
                                 int height = jpeg::kObservedHeight,
                                 int fps = kTargetFps);

/// Refuse a frame whose size does not match the protocol's declared size.
void validate_frame_geometry(int width, int height,
                             int expected_width = jpeg::kObservedWidth,
                             int expected_height = jpeg::kObservedHeight);

/// Supplies encoded JPEG frame payloads.
class FrameSource {
 public:
  virtual ~FrameSource() = default;
  virtual Bytes next_payload() = 0;
  virtual void close() {}

  /// How many frames have been pulled from a PipeWire stream.
  ///
  /// Nonzero is the host's proof that something is consuming the stream, which
  /// is what makes absolute motion land. A source that does not read from
  /// PipeWire reports zero and therefore never provides that proof -- which is
  /// correct, not a limitation: it genuinely is not a consumer.
  virtual std::uint64_t pipewire_frames_captured() const { return 0; }
};

/// A fixed solid colour. Used to prove the wire path without a compositor.
class SolidColourSource : public FrameSource {
 public:
  SolidColourSource(std::uint8_t red = 0, std::uint8_t green = 0,
                    std::uint8_t blue = 0,
                    int width = jpeg::kObservedWidth,
                    int height = jpeg::kObservedHeight);
  Bytes next_payload() override;

 private:
  Bytes payload_;
};

/// Captures from a PipeWire node through GStreamer.
///
/// **Never executed.** The pipeline is the one the Python reference ran in
/// FED-HOST-E001, but this implementation of it has not been started.
class PipeWireFrameSource : public FrameSource {
 public:
  struct Options {
    int node_id = 0;
    int width = jpeg::kObservedWidth;
    int height = jpeg::kObservedHeight;
    int fps = kTargetFps;
    /// How long to wait for the *first* frame. Only never receiving one is a
    /// genuine failure.
    double first_frame_timeout_s = 10.0;
    /// How long to wait for each later frame before repeating the last one.
    double poll_timeout_s = 0.1;
  };

  explicit PipeWireFrameSource(Options options);
  ~PipeWireFrameSource() override;

  PipeWireFrameSource(const PipeWireFrameSource&) = delete;
  PipeWireFrameSource& operator=(const PipeWireFrameSource&) = delete;

  /// Build the pipeline and set it playing.
  void start();

  /// The next frame, or the previous one repeated.
  ///
  /// **The stream negotiates framerate=0/1 with max-framerate=30/1 -- it is
  /// damage-driven.** Mutter produces a buffer only when the screen changes, so
  /// an idle desktop yields none at all. That is correct for a screen cast and
  /// wrong for a display: the iPad still needs frames. A timeout once the
  /// stream is running therefore means "nothing changed", and the answer is to
  /// re-send the last frame rather than to error.
  Bytes next_payload() override;

  void close() override;

  std::uint64_t frames_captured() const { return frames_captured_; }
  std::uint64_t frames_repeated() const { return frames_repeated_; }
  std::uint64_t pipewire_frames_captured() const override {
    return frames_captured_;
  }

 private:
  struct Impl;
  Options options_;
  std::unique_ptr<Impl> impl_;
  jpeg::Encoder encoder_;
  Bytes last_payload_;
  bool have_last_ = false;
  std::uint64_t frames_captured_ = 0;
  std::uint64_t frames_repeated_ = 0;
};

}  // namespace hashi::capture
