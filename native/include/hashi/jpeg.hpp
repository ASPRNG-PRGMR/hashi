// JPEG frame prelude for the observed image stream (FED-JPEG-E001).
//
// Every one of the 1,903 captured image records opens with an identical
// 623-byte prelude: a 609-byte header (APP0, two DQT, SOF0, four DHT) whose
// SHA-256 is
//   3aa000d1d348c7176c24fc4c1cbb12b2172bb5e95689cfeb68008d38dc5f65ad
// followed by a 14-byte SOS. Only the entropy-coded scan data and the trailing
// EOI differ between frames.
//
// Every byte of it is derivable from published standards plus two parameters,
// which is what keeps this clean-room: the four Huffman tables are exactly the
// ISO/IEC 10918-1 Annex K tables, the two quantization tables are the Annex K
// base tables scaled by the standard IJG formula at quality 80, and the frame
// is 1280x960 at 4:2:0. Nothing here transcribes vendor data — this
// *constructs* the prelude from the published tables, and the Python reference
// module it mirrors asserts that the result reproduces the captured bytes.
//
// This half of the JPEG layer is dependency-free: it builds and parses marker
// bytes only. The entropy coder lives in encoder.hpp, which links
// libjpeg-turbo.
#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include "hashi/bytes.hpp"

namespace hashi::jpeg {

// --- Observed parameters ---------------------------------------------------

constexpr int kObservedQuality = 80;
constexpr int kObservedWidth = 1280;
constexpr int kObservedHeight = 960;
/// JFIF APP0 density observed in every frame (units = 1, i.e. dpi).
constexpr int kObservedDensity = 120;
constexpr std::size_t kObservedHeaderLen = 609;
constexpr std::size_t kObservedPreludeLen = 623;

// --- Published ISO/IEC 10918-1 Annex K tables ------------------------------

extern const std::array<std::uint8_t, 16> kDcLumaCounts;
extern const std::array<std::uint8_t, 12> kDcLumaValues;
extern const std::array<std::uint8_t, 16> kDcChromaCounts;
extern const std::array<std::uint8_t, 12> kDcChromaValues;
extern const std::array<std::uint8_t, 16> kAcLumaCounts;
extern const std::array<std::uint8_t, 162> kAcLumaValues;
extern const std::array<std::uint8_t, 16> kAcChromaCounts;
extern const std::array<std::uint8_t, 162> kAcChromaValues;

/// Annex K base quantization tables, in natural (row-major) order.
extern const std::array<std::uint16_t, 64> kBaseLumaQTable;
extern const std::array<std::uint16_t, 64> kBaseChromaQTable;

/// Zig-zag scan order, as DQT segments store coefficients.
extern const std::array<std::uint8_t, 64> kZigzag;

// --- Builders --------------------------------------------------------------

/// Scale an Annex K base table by the standard IJG quality formula.
///
/// At quality 80 this reproduces the captured tables exactly, on all 64
/// coefficients of both tables — an exact match, not an approximation.
/// Throws ProtocolError unless 1 <= quality <= 100.
std::array<std::uint8_t, 64> scale_qtable(
    const std::array<std::uint16_t, 64>& base, int quality);

/// One DQT segment: 8-bit precision, coefficients in zig-zag order.
Bytes build_dqt(const std::array<std::uint16_t, 64>& base, int table_id,
                int quality);

/// One DHT segment. ``table_class`` 0 = DC, 1 = AC.
Bytes build_dht(int table_class, int table_id, const std::uint8_t* counts,
                std::size_t counts_len, const std::uint8_t* values,
                std::size_t values_len);

/// SOF0 for 8-bit, three-component, 4:2:0 content.
///
/// The captured SOF0 declares precision 8 and sampling factors 0x22/0x11/0x11
/// with quantization selectors 0, 1, 1.
Bytes build_sof0(int width, int height);

/// JFIF APP0 as observed: version 1.01, units = 1 (dpi), no thumbnail.
Bytes build_app0(int density = kObservedDensity);

/// SOS as observed: three components, DC/AC selectors 0/0, 1/1, 1/1.
Bytes build_sos();

/// The full SOI..SOS prelude in the observed segment order.
///
/// That order is APP0, DQT(0), DQT(1), SOF0, DHT(0x00), DHT(0x10), DHT(0x01),
/// DHT(0x11), SOS. With the default arguments this returns the captured 623
/// bytes exactly.
Bytes build_prelude(int width = kObservedWidth, int height = kObservedHeight,
                    int quality = kObservedQuality,
                    int density = kObservedDensity);

// --- Parsing ---------------------------------------------------------------

struct Segment {
  std::uint8_t marker;
  std::size_t offset;
  std::size_t length;
};

/// Walk a frame's marker segments up to and including SOS.
std::vector<Segment> parse_segments(const std::uint8_t* data, std::size_t len);

}  // namespace hashi::jpeg
