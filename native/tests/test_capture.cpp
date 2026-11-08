// Tests for the capture layer that need no compositor.
//
// The pipeline description and the geometry check are pure, and the solid
// colour source only encodes. Anything that would start a pipeline or pull from
// a PipeWire node is absent: that is the first live run of this
// implementation, and it has not happened.
#include "testing.hpp"

#include <string>

#include "hashi/capture.hpp"

using namespace hashi;

TEST("capture: the pipeline pins the geometry the prelude declares") {
  const std::string description = capture::pipeline_description(7);
  CHECK(description.find("pipewiresrc path=7") != std::string::npos);
  CHECK(description.find("width=1280,height=960") != std::string::npos);
  CHECK(description.find("format=RGB") != std::string::npos);
  // videoconvert is unconditional: the compositor's buffers are typically
  // BGRx or BGRA, and the encoder wants RGB.
  CHECK(description.find("videoconvert") != std::string::npos);
  // Newest frame rather than accumulated latency, which suits a display.
  CHECK(description.find("max-buffers=1 drop=true") != std::string::npos);
  CHECK(description.find("sync=false") != std::string::npos);
  // The sink has to be findable by name once the pipeline is parsed.
  CHECK(description.find("appsink name=sink") != std::string::npos);
}

TEST("capture: node id zero is valid, negative is not") {
  // PipeWire node ids start at 0, so rejecting 0 would reject a legal node.
  CHECK(capture::pipeline_description(0).find("path=0") != std::string::npos);
  CHECK_THROWS(capture::pipeline_description(-1));
}

TEST("capture: an impossible pipeline is refused before GStreamer sees it") {
  CHECK_THROWS(capture::pipeline_description(1, 0, 960));
  CHECK_THROWS(capture::pipeline_description(1, 1280, 0));
  CHECK_THROWS(capture::pipeline_description(1, 1280, 960, 0));
  CHECK_THROWS(capture::pipeline_description(1, 1280, 960, -30));
}

TEST("capture: a frame of the wrong size is refused, not resized") {
  capture::validate_frame_geometry(1280, 960);
  // The prelude's SOF0 hard-codes the size, so anything else is unsendable.
  CHECK_THROWS(capture::validate_frame_geometry(1920, 1080));
  CHECK_THROWS(capture::validate_frame_geometry(1280, 961));
  // A scaled monitor is the likely cause, so a halved size must fail too
  // rather than look like a plausible frame.
  CHECK_THROWS(capture::validate_frame_geometry(640, 480));
  // An explicitly different expectation is honoured.
  capture::validate_frame_geometry(640, 480, 640, 480);
}

TEST("capture: a solid source encodes one reusable frame") {
  capture::SolidColourSource source;
  const Bytes first = source.next_payload();
  // The captured stream's first record is a solid black 1280x960 screen.
  CHECK_EQ(first.size(), std::size_t{19827});
  // Repeated calls hand back the same bytes rather than re-encoding.
  CHECK_EQ(source.next_payload(), first);
}

TEST("capture: a solid source honours its colour and size") {
  capture::SolidColourSource white(255, 255, 255, 64, 48);
  const Bytes frame = white.next_payload();
  CHECK_EQ(frame[0], std::uint8_t{0xFF});
  CHECK_EQ(frame[1], std::uint8_t{0xD8});
  const auto segments = jpeg::parse_segments(frame.data(), frame.size());
  CHECK_EQ(segments.back().marker, std::uint8_t{0xDA});
  // SOF0 carries the requested size: height then width.
  for (const auto& segment : segments) {
    if (segment.marker != 0xC0) continue;
    const std::size_t at = segment.offset;
    CHECK_EQ(static_cast<int>(frame[at + 5]) << 8 | frame[at + 6], 48);
    CHECK_EQ(static_cast<int>(frame[at + 7]) << 8 | frame[at + 8], 64);
  }
}

TEST("capture: a PipeWire source validates its options at construction") {
  capture::PipeWireFrameSource::Options bad_node;
  bad_node.node_id = -1;
  CHECK_THROWS(capture::PipeWireFrameSource(bad_node));

  capture::PipeWireFrameSource::Options bad_size;
  bad_size.width = 0;
  CHECK_THROWS(capture::PipeWireFrameSource(bad_size));

  capture::PipeWireFrameSource::Options bad_timeout;
  bad_timeout.poll_timeout_s = 0.0;
  CHECK_THROWS(capture::PipeWireFrameSource(bad_timeout));
}

TEST("capture: pulling before start is refused") {
  capture::PipeWireFrameSource::Options options;
  options.node_id = 1;
  capture::PipeWireFrameSource source(options);
  CHECK_THROWS(source.next_payload());
  CHECK_EQ(source.frames_captured(), std::uint64_t{0});
  CHECK_EQ(source.frames_repeated(), std::uint64_t{0});
  // Closing something that never started must be harmless.
  source.close();
}

int main() { return ::testing::run_all(); }
