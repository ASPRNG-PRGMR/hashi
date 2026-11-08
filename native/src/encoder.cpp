#include "hashi/encoder.hpp"

#include <turbojpeg.h>

#include <string>
#include <utility>

namespace hashi::jpeg {

namespace {

/// The TurboJPEG subsampling constant for 4:2:0, matching the observed SOF0
/// sampling factors 0x22/0x11/0x11.
constexpr int kSubsamp420 = TJSAMP_420;

std::string last_error(tjhandle handle) {
  const char* message = tj3GetErrorStr(handle);
  return message != nullptr ? std::string(message) : std::string("unknown");
}

}  // namespace

Encoder::Encoder(int quality, int density)
    : quality_(quality), density_(density) {
  if (quality < 1 || quality > 100) {
    throw EncodeError("quality must be 1..100, got " +
                      std::to_string(quality));
  }
  if (density < 1 || density > 0xFFFF) {
    throw EncodeError("invalid density " + std::to_string(density));
  }
  tjhandle handle = tj3Init(TJINIT_COMPRESS);
  if (handle == nullptr) throw EncodeError("tj3Init failed");
  handle_ = handle;

  // Each of these five parameters is required for byte-identity with the
  // reference. Quality and subsampling set the quantization tables and the
  // chroma geometry; the three density parameters are what put 120 dpi in the
  // JFIF APP0 segment, which the captured frames carry and which TurboJPEG
  // would otherwise write as "no units, 1x1".
  const bool ok =
      tj3Set(handle, TJPARAM_QUALITY, quality) == 0 &&
      tj3Set(handle, TJPARAM_SUBSAMP, kSubsamp420) == 0 &&
      tj3Set(handle, TJPARAM_DENSITYUNITS, 1) == 0 &&
      tj3Set(handle, TJPARAM_XDENSITY, density) == 0 &&
      tj3Set(handle, TJPARAM_YDENSITY, density) == 0;
  if (!ok) {
    const std::string why = last_error(handle);
    tj3Destroy(handle);
    handle_ = nullptr;
    throw EncodeError("tj3Set failed: " + why);
  }
}

Encoder::~Encoder() {
  if (handle_ != nullptr) tj3Destroy(static_cast<tjhandle>(handle_));
}

Encoder::Encoder(Encoder&& other) noexcept
    : handle_(other.handle_),
      quality_(other.quality_),
      density_(other.density_) {
  other.handle_ = nullptr;
}

Encoder& Encoder::operator=(Encoder&& other) noexcept {
  if (this != &other) {
    if (handle_ != nullptr) tj3Destroy(static_cast<tjhandle>(handle_));
    handle_ = other.handle_;
    quality_ = other.quality_;
    density_ = other.density_;
    other.handle_ = nullptr;
  }
  return *this;
}

Bytes Encoder::encode_rgb(const std::uint8_t* rgb, int width, int height) {
  if (handle_ == nullptr) throw EncodeError("encoder has been moved from");
  if (rgb == nullptr) throw EncodeError("null pixel buffer");
  if (width < 1 || width > 0xFFFF || height < 1 || height > 0xFFFF) {
    throw EncodeError("invalid dimensions " + std::to_string(width) + "x" +
                      std::to_string(height));
  }
  auto handle = static_cast<tjhandle>(handle_);

  // tj3Compress8 allocates the output buffer. Freeing it on every path,
  // including the throwing one, is the whole reason for the guard below.
  unsigned char* out = nullptr;
  std::size_t size = 0;
  const int rc = tj3Compress8(handle, rgb, width, /*pitch=*/0, height,
                              TJPF_RGB, &out, &size);
  struct Guard {
    unsigned char* p;
    ~Guard() { if (p != nullptr) tj3Free(p); }
  } guard{out};
  if (rc != 0) throw EncodeError("tj3Compress8 failed: " + last_error(handle));
  return Bytes(out, out + size);
}

Bytes Encoder::encode_rgb(const Bytes& rgb, int width, int height) {
  const auto expected =
      static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * 3;
  if (rgb.size() != expected) {
    throw EncodeError("expected " + std::to_string(expected) +
                      " bytes of RGB for " + std::to_string(width) + "x" +
                      std::to_string(height) + ", got " +
                      std::to_string(rgb.size()));
  }
  return encode_rgb(rgb.data(), width, height);
}

Bytes encode_frame(const std::uint8_t* rgb, int width, int height, int quality,
                   int density) {
  Encoder encoder(quality, density);
  return encoder.encode_rgb(rgb, width, height);
}

}  // namespace hashi::jpeg
