// Outbound frame encoding: raw RGB to a baseline JPEG frame payload.
//
// This closes the entropy-coder question without writing one. libjpeg-turbo,
// driven at quality 80, 4:2:0 subsampling and JFIF density 120, produces a
// prelude byte-identical to the captured one — and for the captured frame
// whose source pixels could be reconstructed (a solid black 1280x960 screen,
// the stream's first record) the entire 19,827-byte frame is byte-identical,
// scan data included, SHA-256 317955d8...
//
// The Python reference reaches libjpeg-turbo through Pillow. This reaches the
// same library through its own TurboJPEG API, and native/tools/conformance.py
// checks the two agree on *bytes* for a set of fixture images rather than
// trusting that both "use libjpeg". They do agree, including on heavy-AC noise
// and on chroma edges, which is where two configurations of the same library
// would diverge if they differed in DCT method or chroma downsampling.
//
// Interoperability note: matching the vendor's tables is not required to talk
// to the device. JPEG is self-describing — every frame carries its own DQT and
// DHT. Reproducing the observed ones is the lowest-risk choice and makes
// offline validation exact.
//
// Unlike the rest of the protocol core, this translation unit links
// libjpeg-turbo.
#pragma once

#include <cstdint>

#include "hashi/bytes.hpp"
#include "hashi/jpeg.hpp"

namespace hashi::jpeg {

/// Raised when libjpeg-turbo reports a failure.
class EncodeError : public std::runtime_error {
 public:
  explicit EncodeError(const std::string& what) : std::runtime_error(what) {}
};

/// A reusable libjpeg-turbo compressor, configured for the observed stream.
///
/// RAII throughout: the TurboJPEG handle and every buffer it hands back are
/// owned here. The port chose C++17 partly because the live layers juggle a
/// D-Bus connection, two sessions, a pipeline and a socket, and the faults the
/// first live run produced were teardown-ordering ones — so nothing in the
/// native tree holds a raw resource.
class Encoder {
 public:
  /// Configure for the observed parameters. Throws EncodeError on failure.
  explicit Encoder(int quality = kObservedQuality,
                   int density = kObservedDensity);
  ~Encoder();

  Encoder(const Encoder&) = delete;
  Encoder& operator=(const Encoder&) = delete;
  Encoder(Encoder&& other) noexcept;
  Encoder& operator=(Encoder&& other) noexcept;

  /// Encode tightly packed 8-bit RGB into a complete JPEG frame payload.
  ///
  /// ``rgb`` must hold exactly ``width * height * 3`` bytes. The result is a
  /// full SOI..EOI frame, ready to be wrapped by encode_image_record.
  Bytes encode_rgb(const std::uint8_t* rgb, int width, int height);

  Bytes encode_rgb(const Bytes& rgb, int width, int height);

  int quality() const { return quality_; }
  int density() const { return density_; }

 private:
  void* handle_ = nullptr;  // tjhandle; opaque so callers need no TurboJPEG
  int quality_;
  int density_;
};

/// Encode one frame with a throwaway encoder. Convenient for tests and tools;
/// a steady-state loop should keep an Encoder alive instead.
Bytes encode_frame(const std::uint8_t* rgb, int width, int height,
                   int quality = kObservedQuality,
                   int density = kObservedDensity);

}  // namespace hashi::jpeg
