// Encode one raw-RGB fixture to a JPEG frame on stdout.
//
// native/tools/conformance.py builds the same fixture, encodes it with the
// Python reference (Pillow over libjpeg-turbo), and diffs the bytes. A whole
// frame is compared, scan data included, so this checks the entropy coder's
// output and not just the prelude.
//
// Usage:  dump_frame <fixture.rgb> <width> <height> [quality] [density]
// Writes the frame to stdout; exits non-zero with a message on stderr.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "hashi/encoder.hpp"

namespace {

int fail(const std::string& message) {
  std::fprintf(stderr, "dump_frame: %s\n", message.c_str());
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 4 || argc > 6) {
    return fail("usage: dump_frame <fixture.rgb> <width> <height> "
                "[quality] [density]");
  }
  const int width = std::atoi(argv[2]);
  const int height = std::atoi(argv[3]);
  const int quality =
      argc > 4 ? std::atoi(argv[4]) : hashi::jpeg::kObservedQuality;
  const int density =
      argc > 5 ? std::atoi(argv[5]) : hashi::jpeg::kObservedDensity;
  if (width < 1 || height < 1) return fail("width and height must be >= 1");

  const auto expected =
      static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * 3;
  std::vector<std::uint8_t> rgb(expected);

  std::FILE* input = std::fopen(argv[1], "rb");
  if (input == nullptr) return fail(std::string("cannot open ") + argv[1]);
  const std::size_t read = std::fread(rgb.data(), 1, expected, input);
  // A short fixture would silently encode uninitialised pixels, which would
  // make a mismatch look like an encoder disagreement.
  const bool overlong = std::fgetc(input) != EOF;
  std::fclose(input);
  if (read != expected) {
    return fail("expected " + std::to_string(expected) + " bytes, read " +
                std::to_string(read));
  }
  if (overlong) {
    return fail("fixture is longer than " + std::to_string(expected) +
                " bytes");
  }

  try {
    hashi::jpeg::Encoder encoder(quality, density);
    const auto frame = encoder.encode_rgb(rgb, width, height);
    if (std::fwrite(frame.data(), 1, frame.size(), stdout) != frame.size()) {
      return fail("short write to stdout");
    }
  } catch (const std::exception& error) {
    return fail(error.what());
  }
  return 0;
}
