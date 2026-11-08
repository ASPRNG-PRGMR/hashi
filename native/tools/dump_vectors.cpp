// Emits the C++ core's wire bytes as `name hex` lines, for conformance.cpp's
// Python counterpart to diff against.
//
// The point is not that the two implementations pass similar tests, but that
// they produce the same bytes. The Python side is the reference: it is what
// reproduced the captured 130,375,177-byte stream byte-for-byte and what
// drove the device in FED-LIVE-E001 and FED-HOST-E001.
#include <cstdio>
#include <string>

#include "hashi/capture.hpp"
#include "hashi/gnome.hpp"
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

  // --- Mutter D-Bus arguments and injection plans -----------------------
  // Compared as a canonical text form rather than as bytes: GLib builds the
  // actual message, so what matters is that both implementations decide on the
  // same signatures, keys, defaults and values. This is where a port degrades
  // quietly -- a uint32 cursor mode sent as an int32, or a default that drifts.
  {
    const std::string stream = "/org/gnome/Mutter/ScreenCast/Stream/u0";
    auto emit_text = [](const std::string& name, const std::string& text) {
      std::printf("%s %s\n", name.c_str(), text.c_str());
    };

    emit_text("gnome_mode_default", gnome::canonical(gnome::virtual_monitor_mode()));
    // A zero rate omits the key; Mutter then defaults the rate to 60.0.
    emit_text("gnome_mode_no_refresh",
              gnome::canonical(gnome::virtual_monitor_mode(1280, 960, 0.0)));
    emit_text("gnome_mode_custom",
              gnome::canonical(gnome::virtual_monitor_mode(640, 480, 59.94, false)));

    emit_text("gnome_record_virtual_default",
              gnome::canonical(gnome::record_virtual_properties()));
    emit_text("gnome_record_virtual_cursor_hidden",
              gnome::canonical(gnome::record_virtual_properties(
                  {}, gnome::kCursorModeHidden)));
    emit_text("gnome_record_virtual_platform_true",
              gnome::canonical(gnome::record_virtual_properties(
                  {}, gnome::kCursorModeEmbedded, 1)));
    emit_text("gnome_record_virtual_platform_false",
              gnome::canonical(gnome::record_virtual_properties(
                  {}, gnome::kCursorModeEmbedded, 0)));

    emit_text("gnome_session_props_empty",
              gnome::canonical(gnome::screen_cast_session_properties()));
    emit_text("gnome_session_props_id",
              gnome::canonical(gnome::screen_cast_session_properties("17")));
    emit_text("gnome_session_props_both",
              gnome::canonical(gnome::screen_cast_session_properties("17", 1)));

    // One line per planned call, joined, so an extra or missing call shows up.
    auto emit_plan = [&](const std::string& name, int field0, int x, int y) {
      const auto plan = gnome::plan_injection(field0, x, y, stream);
      std::string text = "[";
      for (std::size_t i = 0; i < plan.size(); ++i) {
        if (i != 0) text += ",";
        text += gnome::canonical(plan[i]);
      }
      text += "]";
      std::printf("%s %s\n", name.c_str(), text.c_str());
    };

    emit_plan("gnome_inject_down", 5, 100, 200);
    emit_plan("gnome_inject_up", 6, 100, 200);
    emit_plan("gnome_inject_motion", 10, 640, 480);
    emit_plan("gnome_inject_right_down", 8, 1, 2);
    emit_plan("gnome_inject_right_up", 9, 1, 2);
    emit_plan("gnome_inject_middle_down", 14, 3, 4);
    emit_plan("gnome_inject_middle_up", 15, 3, 4);
    emit_plan("gnome_inject_move_only_4", 4, 5, 6);
    emit_plan("gnome_inject_move_only_7", 7, 5, 6);
    // Origin and the far corner: both are inside the display, inclusive.
    emit_plan("gnome_inject_origin", 10, 0, 0);
    emit_plan("gnome_inject_corner", 10, 1280, 960);
    // Values with no pointer meaning must plan nothing at all.
    emit_plan("gnome_inject_keyboard_1", 1, 10, 10);
    emit_plan("gnome_inject_keyboard_2", 2, 10, 10);
    emit_plan("gnome_inject_control_16", 16, 10, 10);
    emit_plan("gnome_inject_control_17", 17, 10, 10);
    emit_plan("gnome_inject_unseen_11", 11, 10, 10);
  }

  // --- Capture pipeline -------------------------------------------------
  // The description is a plain string, so it is compared exactly. A drifted
  // property here -- a missing always-copy, a dropped drop=true -- would
  // change the capture's behaviour without changing any byte on the wire,
  // which is the kind of difference a protocol test would never catch.
  std::printf("pipeline_default %s\n",
              capture::pipeline_description(42).c_str());
  std::printf("pipeline_custom %s\n",
              capture::pipeline_description(0, 640, 480, 60).c_str());

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
