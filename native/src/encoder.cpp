#include "hashi/encoder.hpp"

#include <turbojpeg.h>

#include <cstring>
#include <string>
#include <utility>

// Two TurboJPEG APIs, one encoder.
//
// libjpeg-turbo 3.0 replaced the tjInitCompress/tjCompress2 family with
// tj3Init/tj3Set/tj3Compress8 and did not keep a compatibility macro, so a
// file written against the newer one simply fails to compile where only 2.x is
// installed -- which is still most long-term distributions: Debian 12, Ubuntu
// 22.04 and 24.04, RHEL 9. CI building on one of those is what exposed this.
//
// Both paths are therefore present, and CMake selects between them from the
// pkg-config version by defining HASHI_HAVE_TURBOJPEG3. The difference is
// confined to the four shims below; everything after them is shared, so there
// is only one copy of the validation, the RAII and the buffer handling.
//
// The legacy path is not merely "close enough". Two corrections are needed to
// make it produce the same bytes, and both were found by encoding the same
// pixels through both paths and comparing:
//
//   1. TJFLAG_ACCURATEDCT. TurboJPEG 2.x defaults compression to the *fast*
//      integer DCT, which is why TJFLAG_ACCURATEDCT exists; 3.x flipped the
//      default, so TJPARAM_FASTDCT defaults to off. Without the flag the
//      headers still match and only the scan data diverges -- the quietest
//      possible way to lose byte-identity.
//   2. The JFIF density. 2.x has no API for it at all, so it is written into
//      the APP0 segment afterwards. tj3Set(TJPARAM_DENSITY*) is the only
//      reason the newer API is preferred when it is available.
//
// With those two, the paths agree byte-for-byte: 132 cases -- six frame sizes
// including 1280x960 and a 1x1 degenerate, quality 1/50/80/100, density
// 1/72/120/300/65535, over random noise, a flat black frame and a gradient --
// zero mismatches. The conformance harness then re-checks the selected path
// against Pillow's bytes, so whichever one a given machine compiles is still
// held to the Python reference rather than to the other path.

namespace hashi::jpeg {

namespace {

/// The TurboJPEG subsampling constant for 4:2:0, matching the observed SOF0
/// sampling factors 0x22/0x11/0x11.
constexpr int kSubsamp420 = TJSAMP_420;

#if HASHI_HAVE_TURBOJPEG3

std::string last_error(tjhandle handle) {
  const char* message = tj3GetErrorStr(handle);
  return message != nullptr ? std::string(message) : std::string("unknown");
}

void destroy_handle(tjhandle handle) { tj3Destroy(handle); }

void free_buffer(unsigned char* buffer) { tj3Free(buffer); }

/// Create a compressor with every parameter already applied.
///
/// Each of these five is required for byte-identity with the reference.
/// Quality and subsampling set the quantization tables and the chroma
/// geometry; the three density parameters are what put 120 dpi in the JFIF
/// APP0 segment, which the captured frames carry and which TurboJPEG would
/// otherwise write as "no units, 1x1".
tjhandle open_handle(int quality, int density) {
  tjhandle handle = tj3Init(TJINIT_COMPRESS);
  if (handle == nullptr) throw EncodeError("tj3Init failed");
  const bool ok = tj3Set(handle, TJPARAM_QUALITY, quality) == 0 &&
                  tj3Set(handle, TJPARAM_SUBSAMP, kSubsamp420) == 0 &&
                  tj3Set(handle, TJPARAM_DENSITYUNITS, 1) == 0 &&
                  tj3Set(handle, TJPARAM_XDENSITY, density) == 0 &&
                  tj3Set(handle, TJPARAM_YDENSITY, density) == 0;
  if (!ok) {
    const std::string why = last_error(handle);
    destroy_handle(handle);
    throw EncodeError("tj3Set failed: " + why);
  }
  return handle;
}

/// Compress one frame. The buffer comes back owned by the caller.
Bytes compress(tjhandle handle, const std::uint8_t* rgb, int width, int height,
               int /*quality*/, int /*density*/) {
  unsigned char* out = nullptr;
  std::size_t size = 0;
  const int rc = tj3Compress8(handle, rgb, width, /*pitch=*/0, height,
                              TJPF_RGB, &out, &size);
  // tj3Compress8 allocates the output buffer. Freeing it on every path,
  // including the throwing one, is the whole reason for the guard below.
  struct Guard {
    unsigned char* p;
    ~Guard() {
      if (p != nullptr) free_buffer(p);
    }
  } guard{out};
  if (rc != 0) throw EncodeError("tj3Compress8 failed: " + last_error(handle));
  return Bytes(out, out + size);
}

#else  // legacy TurboJPEG 2.x

std::string last_error(tjhandle handle) {
  const char* message = tjGetErrorStr2(handle);
  return message != nullptr ? std::string(message) : std::string("unknown");
}

void destroy_handle(tjhandle handle) { tjDestroy(handle); }

void free_buffer(unsigned char* buffer) { tjFree(buffer); }

/// Create a compressor. Nothing can be configured up front here: quality,
/// subsampling and the DCT choice are all arguments to tjCompress2, and
/// density has no API at all.
tjhandle open_handle(int /*quality*/, int /*density*/) {
  tjhandle handle = tjInitCompress();
  if (handle == nullptr) throw EncodeError("tjInitCompress failed");
  return handle;
}

/// Write the JFIF density into an already-encoded frame.
///
/// libjpeg emits APP0 first and at a fixed layout, so the three fields sit at
/// known offsets: SOI(2) FFE0(2) length(2) "JFIF\0"(5) version(2) then units
/// at 13 and the two 16-bit big-endian densities at 14 and 16. The shape is
/// checked rather than assumed -- if a future libjpeg-turbo stops leading with
/// JFIF APP0 this must fail loudly, not silently patch whatever is at byte 13.
void patch_jfif_density(Bytes& jpeg, int density) {
  static constexpr std::size_t kUnitsOffset = 13;
  if (jpeg.size() < 18 || jpeg[0] != 0xFF || jpeg[1] != 0xD8 ||
      jpeg[2] != 0xFF || jpeg[3] != 0xE0 ||
      std::memcmp(jpeg.data() + 6, "JFIF\0", 5) != 0) {
    throw EncodeError(
        "encoded frame does not begin with a JFIF APP0 segment, so the "
        "density cannot be set on this libjpeg-turbo");
  }
  const auto hi = static_cast<std::uint8_t>((density >> 8) & 0xFF);
  const auto lo = static_cast<std::uint8_t>(density & 0xFF);
  jpeg[kUnitsOffset] = 1;  // dots per inch
  jpeg[kUnitsOffset + 1] = hi;
  jpeg[kUnitsOffset + 2] = lo;
  jpeg[kUnitsOffset + 3] = hi;
  jpeg[kUnitsOffset + 4] = lo;
}

/// Compress one frame. TJFLAG_ACCURATEDCT is what makes the scan data match
/// 3.x; see the note at the top of the file.
Bytes compress(tjhandle handle, const std::uint8_t* rgb, int width, int height,
               int quality, int density) {
  unsigned char* out = nullptr;
  unsigned long size = 0;  // NOLINT(google-runtime-int) -- tjCompress2's type
  const int rc =
      tjCompress2(handle, rgb, width, /*pitch=*/0, height, TJPF_RGB, &out,
                  &size, kSubsamp420, quality, TJFLAG_ACCURATEDCT);
  struct Guard {
    unsigned char* p;
    ~Guard() {
      if (p != nullptr) free_buffer(p);
    }
  } guard{out};
  if (rc != 0) throw EncodeError("tjCompress2 failed: " + last_error(handle));
  Bytes frame(out, out + size);
  patch_jfif_density(frame, density);
  return frame;
}

#endif  // HASHI_HAVE_TURBOJPEG3

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
  handle_ = open_handle(quality, density);
}

Encoder::~Encoder() {
  if (handle_ != nullptr) destroy_handle(static_cast<tjhandle>(handle_));
}

Encoder::Encoder(Encoder&& other) noexcept
    : handle_(other.handle_),
      quality_(other.quality_),
      density_(other.density_) {
  other.handle_ = nullptr;
}

Encoder& Encoder::operator=(Encoder&& other) noexcept {
  if (this != &other) {
    if (handle_ != nullptr) destroy_handle(static_cast<tjhandle>(handle_));
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
  return compress(static_cast<tjhandle>(handle_), rgb, width, height, quality_,
                  density_);
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
