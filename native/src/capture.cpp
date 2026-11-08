#include "hashi/capture.hpp"

#include <gst/app/gstappsink.h>
#include <gst/gst.h>

#include <string>

namespace hashi::capture {

std::string pipeline_description(int node_id, int width, int height, int fps) {
  if (node_id < 0) {
    throw CaptureError("node_id must be non-negative, got " +
                       std::to_string(node_id));
  }
  if (width <= 0 || height <= 0) {
    throw CaptureError("invalid geometry " + std::to_string(width) + "x" +
                       std::to_string(height));
  }
  if (fps <= 0) {
    throw CaptureError("fps must be positive, got " + std::to_string(fps));
  }
  return "pipewiresrc path=" + std::to_string(node_id) +
         " always-copy=true ! videoconvert ! "
         "video/x-raw,format=RGB,width=" + std::to_string(width) +
         ",height=" + std::to_string(height) +
         " ! appsink name=sink emit-signals=false max-buffers=1 drop=true "
         "sync=false";
}

void validate_frame_geometry(int width, int height, int expected_width,
                            int expected_height) {
  if (width != expected_width || height != expected_height) {
    throw CaptureError(
        "captured frame is " + std::to_string(width) + "x" +
        std::to_string(height) + ", expected " +
        std::to_string(expected_width) + "x" +
        std::to_string(expected_height) +
        "; the JPEG prelude hard-codes the expected size, so this frame "
        "cannot be sent. Check the virtual monitor's pinned mode and whether "
        "the compositor applied a scale.");
  }
}

// --- SolidColourSource -----------------------------------------------------

SolidColourSource::SolidColourSource(std::uint8_t red, std::uint8_t green,
                                     std::uint8_t blue, int width,
                                     int height) {
  Bytes pixels;
  pixels.reserve(static_cast<std::size_t>(width) *
                 static_cast<std::size_t>(height) * 3);
  for (int i = 0; i < width * height; ++i) {
    pixels.push_back(red);
    pixels.push_back(green);
    pixels.push_back(blue);
  }
  jpeg::Encoder encoder;
  payload_ = encoder.encode_rgb(pixels, width, height);
}

Bytes SolidColourSource::next_payload() { return payload_; }

// --- PipeWireFrameSource ---------------------------------------------------

/// The GStreamer handles, kept out of the header so callers need no gst/gst.h.
struct PipeWireFrameSource::Impl {
  GstElement* pipeline = nullptr;
  GstElement* sink = nullptr;

  ~Impl() { teardown(); }

  void teardown() {
    if (pipeline != nullptr) {
      gst_element_set_state(pipeline, GST_STATE_NULL);
    }
    if (sink != nullptr) {
      gst_object_unref(sink);
      sink = nullptr;
    }
    if (pipeline != nullptr) {
      gst_object_unref(pipeline);
      pipeline = nullptr;
    }
  }
};

PipeWireFrameSource::PipeWireFrameSource(Options options)
    : options_(options), impl_(std::make_unique<Impl>()) {
  // Validate now, so a bad node id or geometry is reported before any
  // GStreamer state is built.
  (void)pipeline_description(options_.node_id, options_.width, options_.height,
                             options_.fps);
  if (options_.first_frame_timeout_s <= 0.0 || options_.poll_timeout_s <= 0.0) {
    throw CaptureError("timeouts must be positive");
  }
}

PipeWireFrameSource::~PipeWireFrameSource() = default;

void PipeWireFrameSource::start() {
  if (impl_->pipeline != nullptr) {
    throw CaptureError("capture is already started");
  }
  // In C, appsink's pull methods come from including gst/app/gstappsink.h.
  // The reference carries a note that PyGObject additionally needs GstApp
  // imported or the element has no try_pull_sample; that is a binding artefact
  // with no counterpart here.
  if (gst_is_initialized() == FALSE) {
    gst_init(nullptr, nullptr);
  }
  const std::string description = pipeline_description(
      options_.node_id, options_.width, options_.height, options_.fps);

  GError* error = nullptr;
  GstElement* pipeline = gst_parse_launch(description.c_str(), &error);
  if (error != nullptr) {
    const std::string message =
        error->message != nullptr ? error->message : "unknown error";
    g_error_free(error);
    if (pipeline != nullptr) gst_object_unref(pipeline);
    throw CaptureError("could not build the capture pipeline: " + message);
  }
  if (pipeline == nullptr) {
    throw CaptureError("could not build the capture pipeline");
  }
  impl_->pipeline = pipeline;

  impl_->sink = gst_bin_get_by_name(GST_BIN(pipeline), "sink");
  if (impl_->sink == nullptr) {
    impl_->teardown();
    throw CaptureError("the capture pipeline has no appsink named 'sink'");
  }
  if (gst_element_set_state(pipeline, GST_STATE_PLAYING) ==
      GST_STATE_CHANGE_FAILURE) {
    impl_->teardown();
    throw CaptureError(
        "the capture pipeline refused to start; the PipeWire node may have "
        "gone away, or the pinned caps may not match the stream");
  }
}

Bytes PipeWireFrameSource::next_payload() {
  if (impl_->sink == nullptr) {
    throw CaptureError("capture not started; call start() first");
  }

  const bool first = !have_last_;
  const double timeout_s =
      first ? options_.first_frame_timeout_s : options_.poll_timeout_s;
  const auto timeout_ns =
      static_cast<GstClockTime>(timeout_s * static_cast<double>(GST_SECOND));

  GstSample* sample =
      gst_app_sink_try_pull_sample(GST_APP_SINK(impl_->sink), timeout_ns);
  if (sample == nullptr) {
    if (first) {
      throw CaptureError(
          "no first frame within " + std::to_string(options_.first_frame_timeout_s) +
          "s; the stream never started. Check that the PipeWire node still "
          "exists and that the session was started.");
    }
    // Damage-driven: no buffer means nothing changed, not a fault.
    ++frames_repeated_;
    return last_payload_;
  }

  // One owner for the sample on every path out of here, including the throwing
  // ones below.
  struct SampleGuard {
    GstSample* sample;
    ~SampleGuard() { if (sample != nullptr) gst_sample_unref(sample); }
  } guard{sample};

  GstCaps* caps = gst_sample_get_caps(sample);
  if (caps == nullptr || gst_caps_get_size(caps) == 0) {
    throw CaptureError("the captured sample carries no caps");
  }
  GstStructure* structure = gst_caps_get_structure(caps, 0);
  int width = 0;
  int height = 0;
  if (gst_structure_get_int(structure, "width", &width) == FALSE ||
      gst_structure_get_int(structure, "height", &height) == FALSE) {
    throw CaptureError("the captured caps declare no width or height");
  }
  validate_frame_geometry(width, height, options_.width, options_.height);

  GstBuffer* buffer = gst_sample_get_buffer(sample);
  if (buffer == nullptr) throw CaptureError("the captured sample has no buffer");
  GstMapInfo info;
  if (gst_buffer_map(buffer, &info, GST_MAP_READ) == FALSE) {
    throw CaptureError("could not map the captured buffer");
  }
  struct MapGuard {
    GstBuffer* buffer;
    GstMapInfo* info;
    ~MapGuard() { gst_buffer_unmap(buffer, info); }
  } map_guard{buffer, &info};

  // GStreamer pads each row up to a 4-byte boundary, so a buffer is only
  // densely packed when width * 3 is already a multiple of 4. It is for 1280
  // (3840 bytes), but asserting it beats assuming it: an unnoticed stride
  // would shear the image diagonally rather than fail, which is exactly the
  // kind of fault that wastes a debugging session on the protocol instead of
  // the capture.
  const auto expected = static_cast<std::size_t>(width) *
                        static_cast<std::size_t>(height) * 3;
  if (info.size != expected) {
    throw CaptureError(
        "captured buffer is " + std::to_string(info.size) + " bytes for " +
        std::to_string(width) + "x" + std::to_string(height) +
        " RGB, expected " + std::to_string(expected) +
        ". The rows are padded to a stride of " +
        std::to_string(info.size / static_cast<std::size_t>(height)) +
        " bytes, which this unpacking does not handle.");
  }

  last_payload_ = encoder_.encode_rgb(info.data, width, height);
  have_last_ = true;
  ++frames_captured_;
  return last_payload_;
}

void PipeWireFrameSource::close() { impl_->teardown(); }

}  // namespace hashi::capture
