// Emits the C++ core's wire bytes as `name hex` lines, for conformance.cpp's
// Python counterpart to diff against.
//
// The point is not that the two implementations pass similar tests, but that
// they produce the same bytes. The Python side is the reference: it is what
// reproduced the captured 130,375,177-byte stream byte-for-byte and what
// drove the device in FED-LIVE-E001 and FED-HOST-E001.
#include <cstdio>
#include <string>

#include "hashi/jpeg.hpp"
#include "hashi/startup.hpp"
#include "hashi/stream.hpp"
#include "hashi/usbmux.hpp"

using namespace hashi;

namespace {

void emit(const std::string& name, const Bytes& bytes) {
  std::printf("%s ", name.c_str());
  for (std::uint8_t b : bytes) std::printf("%02x", b);
  std::printf("\n");
}

}  // namespace

int main() {
  // --- startup ----------------------------------------------------------
  emit("probe", startup::encode_byte_order_probe());
  emit("hello", startup::encode_control(startup::kMsgHello));
  emit("ready", startup::encode_control(startup::kMsgReady));
  emit("extra_request",
       startup::encode_control(startup::kMsgExtraRequest, 5, 0, true, true));
  emit("hello_ack_2048x1536",
       startup::encode_control(startup::kMsgHelloAck, 2048, 1536));
  emit("ready_ack", startup::encode_control(startup::kMsgReadyAck));
  emit("legacy_hello", startup::encode_control(startup::kMsgHello, 0, 0, false));
  emit("header_5_12", startup::encode_header(5, 12));
  emit("header_6_19827", startup::encode_header(6, 19827));
  emit("header_6_max", startup::encode_header(6, 0xFFFFFF));

  // --- stream -----------------------------------------------------------
  emit("image_record_small", stream::encode_image_record(Bytes{0xFF, 0xD8, 0xFF, 0xD9}));
  {
    Bytes payload(1000, 0xAB);
    Bytes record = stream::encode_image_record(payload);
    record.resize(8);  // header plus a few bytes is enough to compare framing
    emit("image_record_1000_head", record);
  }

  // --- JPEG frame prelude ----------------------------------------------
  // Marker bytes only: the prelude is built from published Annex K tables, so
  // it is part of the dependency-free core. The entropy coder is compared
  // separately, on whole frames, by dump_frame.
  emit("jpeg_app0", jpeg::build_app0());
  emit("jpeg_app0_density_72", jpeg::build_app0(72));
  emit("jpeg_dqt_luma_q80", jpeg::build_dqt(jpeg::kBaseLumaQTable, 0, 80));
  emit("jpeg_dqt_chroma_q80", jpeg::build_dqt(jpeg::kBaseChromaQTable, 1, 80));
  // Below 50 the IJG formula switches branch, and 100 is the clamp boundary.
  emit("jpeg_dqt_luma_q25", jpeg::build_dqt(jpeg::kBaseLumaQTable, 0, 25));
  emit("jpeg_dqt_luma_q100", jpeg::build_dqt(jpeg::kBaseLumaQTable, 0, 100));
  emit("jpeg_dqt_luma_q1", jpeg::build_dqt(jpeg::kBaseLumaQTable, 0, 1));
  emit("jpeg_sof0_1280x960", jpeg::build_sof0(1280, 960));
  emit("jpeg_sof0_odd", jpeg::build_sof0(17, 5));
  emit("jpeg_dht_dc_luma",
       jpeg::build_dht(0, 0, jpeg::kDcLumaCounts.data(),
                       jpeg::kDcLumaCounts.size(), jpeg::kDcLumaValues.data(),
                       jpeg::kDcLumaValues.size()));
  emit("jpeg_dht_ac_luma",
       jpeg::build_dht(1, 0, jpeg::kAcLumaCounts.data(),
                       jpeg::kAcLumaCounts.size(), jpeg::kAcLumaValues.data(),
                       jpeg::kAcLumaValues.size()));
  emit("jpeg_dht_dc_chroma",
       jpeg::build_dht(0, 1, jpeg::kDcChromaCounts.data(),
                       jpeg::kDcChromaCounts.size(),
                       jpeg::kDcChromaValues.data(),
                       jpeg::kDcChromaValues.size()));
  emit("jpeg_dht_ac_chroma",
       jpeg::build_dht(1, 1, jpeg::kAcChromaCounts.data(),
                       jpeg::kAcChromaCounts.size(),
                       jpeg::kAcChromaValues.data(),
                       jpeg::kAcChromaValues.size()));
  emit("jpeg_sos", jpeg::build_sos());
  emit("jpeg_prelude_observed", jpeg::build_prelude());
  emit("jpeg_prelude_odd", jpeg::build_prelude(17, 5, 25, 72));

  // --- usbmux header framing -------------------------------------------
  // The plist body itself is not compared: usbmuxd parses XML, and the two
  // writers legitimately differ in whitespace. The header is what the
  // protocol pins, so that is what is checked, with the body length removed.
  {
    const Bytes connect = usbmux::build_connect(1);
    Bytes header(connect.begin() + 4, connect.begin() + 16);  // skip length
    emit("connect_header_tail", header);
  }
  std::printf("port_swapped %u\n", usbmux::htons_port(usbmux::kApplicationPort));
  std::printf("align_2048 %u\n", startup::align_client_dimension(2048));
  std::printf("align_1 %u\n", startup::align_client_dimension(1));
  std::printf("align_5 %u\n", startup::align_client_dimension(5));
  std::printf("interval_30 %u\n", stream::frame_interval_ms(30));
  std::printf("interval_60 %u\n", stream::frame_interval_ms(60));
  return 0;
}
