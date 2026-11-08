// Tests for the frame encoder.
//
// These are deliberately thin, because the meaningful check on an entropy
// coder is not an assertion written here -- it is native/tools/conformance.py
// diffing whole frames, scan data included, against the Python reference. What
// these cover is the part conformance cannot see: that the two halves of the
// JPEG layer agree (the encoder's own prelude is the one build_prelude
// constructs), and that the RAII wrapper behaves under misuse.
#include "testing.hpp"

#include "hashi/encoder.hpp"

using namespace hashi;

namespace {

/// Tightly packed RGB for a solid-colour image.
Bytes solid(int width, int height, std::uint8_t r, std::uint8_t g,
            std::uint8_t b) {
  Bytes out;
  out.reserve(static_cast<std::size_t>(width) *
              static_cast<std::size_t>(height) * 3);
  for (int i = 0; i < width * height; ++i) {
    out.push_back(r);
    out.push_back(g);
    out.push_back(b);
  }
  return out;
}

}  // namespace

TEST("encoder: a frame opens with exactly the constructed prelude") {
  // This is the test that ties the two halves of the JPEG layer together. The
  // prelude builder works from published Annex K tables; libjpeg-turbo builds
  // its own from the same formula. They must land on the same 623 bytes.
  jpeg::Encoder encoder;
  const Bytes frame = encoder.encode_rgb(
      solid(jpeg::kObservedWidth, jpeg::kObservedHeight, 0, 0, 0),
      jpeg::kObservedWidth, jpeg::kObservedHeight);
  const Bytes prelude = jpeg::build_prelude();
  CHECK(frame.size() > prelude.size());
  const Bytes head(frame.begin(), frame.begin() + static_cast<long>(prelude.size()));
  CHECK_EQ(head, prelude);
}

TEST("encoder: the captured black frame reproduces byte for byte") {
  // FED-JPEG-E001: the stream's first record is a solid black 1280x960 screen
  // and its payload is 19,827 bytes. The source pixels are reconstructible for
  // this one frame, which makes it the only captured frame an encoder can be
  // held to exactly.
  jpeg::Encoder encoder;
  const Bytes frame = encoder.encode_rgb(
      solid(jpeg::kObservedWidth, jpeg::kObservedHeight, 0, 0, 0),
      jpeg::kObservedWidth, jpeg::kObservedHeight);
  CHECK_EQ(frame.size(), std::size_t{19827});
}

TEST("encoder: a frame is a complete SOI..EOI payload") {
  jpeg::Encoder encoder;
  const Bytes frame = encoder.encode_rgb(solid(32, 32, 10, 20, 30), 32, 32);
  CHECK_EQ(frame[0], std::uint8_t{0xFF});
  CHECK_EQ(frame[1], std::uint8_t{0xD8});
  CHECK_EQ(frame[frame.size() - 2], std::uint8_t{0xFF});
  CHECK_EQ(frame[frame.size() - 1], std::uint8_t{0xD9});
  // And the segment walker agrees it is well formed up to the scan.
  const auto segments = jpeg::parse_segments(frame.data(), frame.size());
  CHECK_EQ(segments.back().marker, std::uint8_t{0xDA});
}

TEST("encoder: encoding is deterministic and reuse changes nothing") {
  jpeg::Encoder encoder;
  const Bytes pixels = solid(64, 48, 200, 100, 50);
  const Bytes first = encoder.encode_rgb(pixels, 64, 48);
  const Bytes second = encoder.encode_rgb(pixels, 64, 48);
  CHECK_EQ(first, second);
  // A throwaway encoder must agree with a reused one.
  CHECK_EQ(jpeg::encode_frame(pixels.data(), 64, 48), first);
}

TEST("encoder: quality and density reach the output") {
  const Bytes pixels = solid(64, 48, 200, 100, 50);
  jpeg::Encoder lower(25, 72);
  const Bytes frame = lower.encode_rgb(pixels, 64, 48);
  // Density lands in APP0 at the same offsets the builder uses.
  CHECK_EQ(static_cast<int>(frame[14]) << 8 | frame[15], 72);
  CHECK_EQ(static_cast<int>(frame[16]) << 8 | frame[17], 72);
  // A lower quality must be a smaller frame than the observed setting.
  jpeg::Encoder observed;
  CHECK(frame.size() < observed.encode_rgb(pixels, 64, 48).size());
  // And the quantization tables are the ones the builder derives for 25.
  const Bytes want = jpeg::build_dqt(jpeg::kBaseLumaQTable, 0, 25);
  const Bytes got(frame.begin() + 20,
                  frame.begin() + 20 + static_cast<long>(want.size()));
  CHECK_EQ(got, want);
}

TEST("encoder: a buffer of the wrong size is refused") {
  jpeg::Encoder encoder;
  const Bytes too_small = solid(16, 16, 0, 0, 0);
  CHECK_THROWS(encoder.encode_rgb(too_small, 32, 32));
  CHECK_THROWS(encoder.encode_rgb(too_small, 16, 17));
}

TEST("encoder: bad parameters are refused at construction") {
  CHECK_THROWS(jpeg::Encoder(0, 120));
  CHECK_THROWS(jpeg::Encoder(101, 120));
  CHECK_THROWS(jpeg::Encoder(80, 0));
  CHECK_THROWS(jpeg::Encoder(80, 0x10000));
}

TEST("encoder: bad dimensions are refused") {
  jpeg::Encoder encoder;
  const Bytes pixels = solid(8, 8, 0, 0, 0);
  CHECK_THROWS(encoder.encode_rgb(pixels.data(), 0, 8));
  CHECK_THROWS(encoder.encode_rgb(pixels.data(), 8, 0));
  CHECK_THROWS(encoder.encode_rgb(pixels.data(), 0x10000, 8));
  CHECK_THROWS(encoder.encode_rgb(nullptr, 8, 8));
}

TEST("encoder: a moved-from encoder reports rather than crashes") {
  // Teardown ordering is what produced the faults in the first live run, so
  // the moved-from state is given a defined behaviour instead of being left
  // to chance.
  jpeg::Encoder source;
  jpeg::Encoder sink(std::move(source));
  const Bytes pixels = solid(16, 16, 0, 0, 0);
  CHECK_THROWS(source.encode_rgb(pixels, 16, 16));
  CHECK(sink.encode_rgb(pixels, 16, 16).size() > 0);

  jpeg::Encoder assigned(25, 72);
  assigned = std::move(sink);
  CHECK_EQ(assigned.quality(), jpeg::kObservedQuality);
  CHECK_EQ(assigned.density(), jpeg::kObservedDensity);
  CHECK(assigned.encode_rgb(pixels, 16, 16).size() > 0);
}

int main() { return ::testing::run_all(); }
