//! Tests for the Rust core.
//!
//! These assert the values taken from the captures — the same values the
//! Python and C++ suites assert — so all three are checked against one source
//! of truth rather than against each other. The byte-level agreement between
//! implementations is checked separately, and more strongly, by
//! `native/tools/conformance.py`.

use hashi::{capture, gnome, jpeg, pacer, plist, startup, stream, usbmux};

// ---------------------------------------------------------------------------
// startup
// ---------------------------------------------------------------------------

#[test]
fn header_is_a_type_byte_then_a_be24_length() {
    assert_eq!(
        startup::encode_header(6, 19827).unwrap(),
        vec![6, 0x00, 0x4D, 0x73]
    );
    // The 24-bit boundary is exactly representable; one more is not.
    assert!(startup::encode_header(6, 0xFF_FFFF).is_ok());
    assert!(startup::encode_header(6, 0x100_0000).is_err());
}

#[test]
fn the_0xfc_record_keeps_its_little_endian_field1() {
    // The agent stores the literal 5 with no htonl (RVA 0x30829) while its
    // siblings are big-endian. This is a reproduction, not a bug: a port that
    // "fixes" it stops matching the capture.
    let record = startup::encode_control(startup::MSG_EXTRA_REQUEST, 5, 0, true, true).unwrap();
    assert_eq!(&record[8..12], &[0x05, 0x00, 0x00, 0x00]);
    // With the swap applied it would be the other way round.
    let swapped = startup::encode_control(startup::MSG_EXTRA_REQUEST, 5, 0, true, false).unwrap();
    assert_eq!(&swapped[8..12], &[0x00, 0x00, 0x00, 0x05]);
}

#[test]
fn only_byte_zero_of_the_probe_reply_is_checked() {
    assert!(startup::probe_reply_accepted(&[4]));
    assert!(startup::probe_reply_accepted(&[4, 0xFF, 0xFF, 0xFF]));
    assert!(!startup::probe_reply_accepted(&[1, 4, 4, 4]));
    assert!(!startup::probe_reply_accepted(&[]));
}

#[test]
fn client_dimensions_round_up_to_a_multiple_of_four() {
    // ((v - 1) & ~3) + 4, which leaves an exact multiple alone.
    assert_eq!(startup::align_client_dimension(2048), 2048);
    assert_eq!(startup::align_client_dimension(1), 4);
    assert_eq!(startup::align_client_dimension(5), 8);
    assert_eq!(startup::align_client_dimension(0), 0);
}

#[test]
fn the_captured_hello_ack_gives_2048x1536() {
    let record = startup::encode_control(startup::MSG_HELLO_ACK, 2048, 1536, true, false).unwrap();
    let dims = startup::parse_hello_ack(&record, true).unwrap();
    assert_eq!(dims.width, 2048);
    assert_eq!(dims.height, 1536);
    // A record whose field0 is not 2 is not a hello ack.
    let wrong = startup::control(startup::MSG_READY).unwrap();
    assert!(startup::parse_hello_ack(&wrong, true).is_err());
}

#[test]
fn an_extra_data_block_of_zero_length_is_refused() {
    assert_eq!(startup::extra_data_length(&[5, 0, 0, 12]).unwrap(), 12);
    assert!(startup::extra_data_length(&[5, 0, 0, 0]).is_err());
}

// ---------------------------------------------------------------------------
// the diff_jpeg gate
// ---------------------------------------------------------------------------

#[test]
fn the_captured_extra_data_block_leaves_diff_jpeg_off() {
    // The capture is 000000fd followed by zeros: not valid JSON, so the parse
    // fails and the gate stays closed. That is why ordinary JPEG ran.
    let mut body = vec![0x00, 0x00, 0x00, 0xFD];
    body.extend(std::iter::repeat(0u8).take(249));
    assert!(!startup::diff_jpeg_enabled(&body));
}

#[test]
fn the_gate_needs_a_valid_document_a_top_level_key_and_boolean_true() {
    assert!(startup::diff_jpeg_enabled(br#"{"diff_jpeg": true}"#));
    // False, absent, or the wrong type all leave it closed.
    assert!(!startup::diff_jpeg_enabled(br#"{"diff_jpeg": false}"#));
    assert!(!startup::diff_jpeg_enabled(br#"{"other": true}"#));
    assert!(!startup::diff_jpeg_enabled(br#"{"diff_jpeg": 1}"#));
    assert!(!startup::diff_jpeg_enabled(br#"{"diff_jpeg": "true"}"#));
    // Nested does not count: the agent reads the key off the root document.
    assert!(!startup::diff_jpeg_enabled(
        br#"{"caps": {"diff_jpeg": true}}"#
    ));
    // A malformed document must fail rather than appear to contain the key,
    // which is why this parses instead of string-matching.
    assert!(!startup::diff_jpeg_enabled(br#"{"diff_jpeg": true"#));
    assert!(!startup::diff_jpeg_enabled(br#"diff_jpeg=true"#));
    // A document must be an object or an array.
    assert!(!startup::diff_jpeg_enabled(b"true"));
    assert!(!startup::diff_jpeg_enabled(b""));
}

// ---------------------------------------------------------------------------
// stream
// ---------------------------------------------------------------------------

#[test]
fn an_image_record_is_its_header_then_its_payload() {
    let record = stream::encode_image_record(&[0xFF, 0xD8, 0xFF, 0xD9]).unwrap();
    assert_eq!(record, vec![6, 0, 0, 4, 0xFF, 0xD8, 0xFF, 0xD9]);
    assert!(stream::encode_image_record(&[]).is_err());
}

#[test]
fn the_frame_interval_truncates_as_the_agent_does() {
    assert_eq!(stream::frame_interval_ms(30).unwrap(), 33);
    assert_eq!(stream::frame_interval_ms(60).unwrap(), 16);
    assert!(stream::frame_interval_ms(0).is_err());
    assert!(stream::frame_interval_ms(-1).is_err());
}

#[test]
fn only_type_seven_payloads_are_byte_swapped() {
    assert!(stream::tlv_payload_is_network_order(stream::TLV_TYPE_7));
    assert!(!stream::tlv_payload_is_network_order(stream::TLV_TYPE_3));
}

/// One observed inbound record: type 7, 16 bytes, big-endian payload.
fn tlv7(field0: u32, x: u32, y: u32) -> Vec<u8> {
    let mut out = vec![7, 0, 0, 12];
    out.extend_from_slice(&field0.to_be_bytes());
    out.extend_from_slice(&x.to_be_bytes());
    out.extend_from_slice(&y.to_be_bytes());
    out
}

#[test]
fn an_observed_drag_reassembles() {
    let mut demuxer = stream::InboundDemuxer::new();
    let mut data = tlv7(5, 100, 100);
    for i in 0..20u32 {
        data.extend(tlv7(10, 100 + i, 100 + i));
    }
    data.extend(tlv7(6, 120, 120));
    let records = demuxer.feed(&data).unwrap();
    assert_eq!(records.len(), 22);
    assert_eq!(records[0].field0, stream::POINTER_DOWN);
    assert_eq!(records[21].field0, stream::POINTER_UP);
    assert_eq!(demuxer.records_seen(), 22);
    assert_eq!(demuxer.pending_bytes(), 0);
}

#[test]
fn a_record_split_across_two_reads_is_held_until_complete() {
    let mut demuxer = stream::InboundDemuxer::new();
    let record = tlv7(10, 640, 480);
    assert!(demuxer.feed(&record[..7]).unwrap().is_empty());
    assert_eq!(demuxer.pending_bytes(), 7);
    let records = demuxer.feed(&record[7..]).unwrap();
    assert_eq!(records.len(), 1);
    assert_eq!(records[0].field1, 640);
    assert_eq!(records[0].field2, 480);
}

#[test]
fn an_overlong_record_is_consumed_in_full_but_parsed_as_twelve() {
    // Keeping and consuming 12 would desynchronise every later record, which
    // makes a stream look corrupt from the second record onward.
    let mut data = vec![7, 0, 0, 20];
    data.extend_from_slice(&10u32.to_be_bytes());
    data.extend_from_slice(&1u32.to_be_bytes());
    data.extend_from_slice(&2u32.to_be_bytes());
    data.extend_from_slice(&[0xEE; 8]); // the 8 bytes beyond the clamp
    data.extend(tlv7(6, 3, 4)); // a following record that must still parse

    let mut demuxer = stream::InboundDemuxer::new();
    let records = demuxer.feed(&data).unwrap();
    assert_eq!(records.len(), 2);
    assert!(records[0].truncated);
    assert_eq!(records[0].field0, 10);
    assert_eq!(records[1].field0, 6);
    assert_eq!(records[1].field1, 3);
}

#[test]
fn a_nonsense_length_is_reported_rather_than_allocated() {
    let mut zero = stream::InboundDemuxer::new();
    assert!(zero.feed(&[7, 0, 0, 0]).is_err());
    let mut huge = stream::InboundDemuxer::new();
    assert!(huge.feed(&[7, 0xFF, 0xFF, 0xFF]).is_err());
}

#[test]
fn field0_maps_to_evdev_buttons_not_win32_flags() {
    assert_eq!(stream::evdev_button_for(5), Some(stream::BTN_LEFT));
    assert_eq!(stream::evdev_button_for(6), Some(stream::BTN_LEFT));
    assert_eq!(stream::BTN_LEFT, 272);
    assert_eq!(stream::button_is_press(5), Some(true));
    assert_eq!(stream::button_is_press(6), Some(false));
    // Motion carries no button.
    assert_eq!(stream::evdev_button_for(10), None);
    assert!(stream::is_pointer_motion(10));
    // Keyboard values are neither.
    assert_eq!(stream::evdev_button_for(1), None);
    assert!(!stream::is_pointer_motion(1));
}

// ---------------------------------------------------------------------------
// usbmux
// ---------------------------------------------------------------------------

#[test]
fn the_application_port_is_carried_byte_swapped() {
    // The capture shows 6789 as 34074.
    assert_eq!(usbmux::htons_port(usbmux::APPLICATION_PORT).unwrap(), 34074);
    assert!(usbmux::htons_port(0).is_err());
}

#[test]
fn a_message_header_is_sixteen_little_endian_bytes() {
    let connect = usbmux::build_connect(1, usbmux::APPLICATION_PORT, 14, None).unwrap();
    let header = usbmux::decode_header(&connect[..16]).unwrap();
    assert_eq!(header.length as usize, connect.len());
    assert_eq!(header.version, usbmux::VERSION_PLIST);
    assert_eq!(header.message, usbmux::MESSAGE_PLIST);
    assert_eq!(header.tag, 14);
    assert!(usbmux::build_connect(-1, usbmux::APPLICATION_PORT, 14, None).is_err());
}

#[test]
fn a_connect_message_round_trips_through_the_plist_subset() {
    let connect = usbmux::build_connect(7, usbmux::APPLICATION_PORT, 14, None).unwrap();
    let (tag, payload) = usbmux::decode_message(&connect).unwrap();
    assert_eq!(tag, 14);
    assert_eq!(payload.get("MessageType").as_string().unwrap(), "Connect");
    assert_eq!(payload.get("DeviceID").as_integer().unwrap(), 7);
    assert_eq!(payload.get("PortNumber").as_integer().unwrap(), 34074);
    assert_eq!(
        payload.get("ClientVersionString").as_string().unwrap(),
        usbmux::CLIENT_VERSION_STRING
    );
}

#[test]
fn the_binary_usbmux_protocol_is_refused_rather_than_guessed() {
    let mut message = usbmux::build_list_devices(1);
    message[8] = 1; // message type 1 is the binary protocol
    assert!(usbmux::decode_message(&message).is_err());
}

#[test]
fn a_device_list_is_parsed_and_the_ipad_selected_by_product_id() {
    let xml = r#"<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>DeviceList</key>
  <array>
    <dict>
      <key>DeviceID</key><integer>11</integer>
      <key>Properties</key>
      <dict>
        <key>ProductID</key><integer>4779</integer>
        <key>SerialNumber</key><string>abc123</string>
        <key>ConnectionType</key><string>USB</string>
      </dict>
    </dict>
  </array>
</dict>
</plist>
"#;
    let payload = plist::loads(xml).unwrap();
    let devices = usbmux::parse_device_list(&payload).unwrap();
    assert_eq!(devices.len(), 1);
    assert_eq!(devices[0].device_id, 11);
    assert_eq!(devices[0].product_id, usbmux::IPAD_PRODUCT_ID as i64);
    assert_eq!(devices[0].serial, "abc123");
    // usbmuxd reassigns DeviceID on every attach, so it must be discovered.
    assert_eq!(
        usbmux::select_device(&devices, Some(usbmux::IPAD_PRODUCT_ID)).unwrap(),
        11
    );
    assert!(usbmux::select_device(&[], Some(usbmux::IPAD_PRODUCT_ID)).is_err());
}

#[test]
fn the_plist_reader_refuses_what_it_does_not_support() {
    // Strict on purpose: a reply shaped differently from the decoded protocol
    // must fail visibly rather than yield a half-parsed value.
    assert!(plist::loads("<plist version=\"1.0\"><real>1.5</real></plist>").is_err());
    assert!(plist::loads("<notplist/>").is_err());
}

#[test]
fn a_result_number_names_itself() {
    let ok = plist::loads(
        "<plist version=\"1.0\"><dict><key>Number</key><integer>0</integer></dict></plist>",
    )
    .unwrap();
    assert!(usbmux::result_is_success(&ok));
    assert_eq!(usbmux::result_name(&ok), "OK");
    let baddev = plist::loads(
        "<plist version=\"1.0\"><dict><key>Number</key><integer>2</integer></dict></plist>",
    )
    .unwrap();
    assert!(!usbmux::result_is_success(&baddev));
    assert_eq!(usbmux::result_name(&baddev), "BADDEV");
}

// ---------------------------------------------------------------------------
// JPEG prelude
// ---------------------------------------------------------------------------

#[test]
fn the_default_prelude_is_the_captured_623_bytes() {
    let prelude = jpeg::observed_prelude().unwrap();
    assert_eq!(prelude.len(), jpeg::OBSERVED_PRELUDE_LEN);
    assert_eq!(
        prelude.len() - jpeg::build_sos().len(),
        jpeg::OBSERVED_HEADER_LEN
    );
    assert_eq!(&prelude[..2], &[0xFF, 0xD8]);
}

#[test]
fn the_prelude_carries_the_observed_segment_order() {
    let prelude = jpeg::observed_prelude().unwrap();
    let markers: Vec<u8> = jpeg::parse_segments(&prelude)
        .unwrap()
        .iter()
        .map(|s| s.marker)
        .collect();
    assert_eq!(
        markers,
        vec![0xD8, 0xE0, 0xDB, 0xDB, 0xC0, 0xC4, 0xC4, 0xC4, 0xC4, 0xDA]
    );
}

#[test]
fn quality_80_scaling_is_the_standard_ijg_formula() {
    // 200 - 2*80 = 40, so each coefficient is (base*40 + 50)/100.
    let scaled = jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 80).unwrap();
    assert_eq!(scaled[0], 6); // (16*40 + 50)/100
    assert_eq!(scaled[1], 4); // (11*40 + 50)/100
    assert_eq!(scaled[63], 40); // (99*40 + 50)/100
}

#[test]
fn the_scaling_branch_below_fifty_and_the_clamps() {
    let low = jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 25).unwrap();
    assert_eq!(low[0], 32); // 5000/25 = 200; (16*200+50)/100
    let worst = jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 1).unwrap();
    assert_eq!(worst[0], 255);
    // Quality 100 gives scale 0, and the floor of 1 keeps the table legal.
    let best = jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 100).unwrap();
    assert_eq!(best[0], 1);
    assert_eq!(best[63], 1);
    assert!(jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 0).is_err());
    assert!(jpeg::scale_qtable(&jpeg::BASE_LUMA_QTABLE, 101).is_err());
}

#[test]
fn sof0_declares_420_with_height_before_width() {
    let sof = jpeg::build_sof0(1280, 960).unwrap();
    assert_eq!(sof.len(), 19);
    assert_eq!(sof[4], 8); // sample precision
    assert_eq!(((sof[5] as i32) << 8) | sof[6] as i32, 960);
    assert_eq!(((sof[7] as i32) << 8) | sof[8] as i32, 1280);
    assert_eq!(sof[11], 0x22); // luma sampling factors: 4:2:0
    assert_eq!(sof[14], 0x11);
    assert_eq!(sof[17], 0x11);
}

#[test]
fn app0_declares_dpi_units_and_the_observed_density() {
    let app0 = jpeg::build_app0(jpeg::OBSERVED_DENSITY).unwrap();
    assert_eq!(app0.len(), 18);
    assert_eq!(app0[11], 1); // units = 1, dots per inch
    assert_eq!(((app0[12] as i32) << 8) | app0[13] as i32, 120);
    assert!(jpeg::build_app0(0).is_err());
}

#[test]
fn a_dht_whose_counts_disagree_with_its_values_is_rejected() {
    let counts = [0u8, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    assert!(jpeg::build_dht(0, 0, &counts, &[0]).is_err());
}

#[test]
fn parse_segments_rejects_malformed_input() {
    assert!(jpeg::parse_segments(&[0, 0, 0, 0]).is_err());
    // A segment claiming more length than there is data.
    assert!(jpeg::parse_segments(&[0xFF, 0xD8, 0xFF, 0xE0, 0xFF, 0xFF]).is_err());
    // A length below the two bytes the field itself occupies.
    assert!(jpeg::parse_segments(&[0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x01]).is_err());
    // No SOS anywhere.
    let mut headerless = vec![0xFF, 0xD8];
    headerless.extend(jpeg::build_app0(120).unwrap());
    assert!(jpeg::parse_segments(&headerless).is_err());
}

// ---------------------------------------------------------------------------
// Mutter contracts
// ---------------------------------------------------------------------------

#[test]
fn only_the_verified_interface_versions_are_accepted() {
    assert!(gnome::check_versions(4, 1).is_ok());
    // A newer version is refused too: a changed `modes` contract would
    // otherwise surface only as wrong-sized frames.
    assert!(gnome::check_versions(5, 1).is_err());
    assert!(gnome::check_versions(3, 1).is_err());
    assert!(gnome::check_versions(4, 2).is_err());
}

#[test]
fn the_device_type_bitmask_is_checked_for_coverage() {
    let all =
        gnome::DEVICE_TYPE_KEYBOARD | gnome::DEVICE_TYPE_POINTER | gnome::DEVICE_TYPE_TOUCHSCREEN;
    assert_eq!(all, 7); // what Mutter 51.1 reports
    assert!(gnome::supports_device_types(
        all,
        gnome::DEVICE_TYPE_POINTER
    ));
    assert!(!gnome::supports_device_types(
        gnome::DEVICE_TYPE_KEYBOARD,
        gnome::DEVICE_TYPE_POINTER
    ));
}

#[test]
fn the_default_mode_pins_1280x960_at_30hz() {
    assert_eq!(
        gnome::canonical_dict(&gnome::observed_mode().unwrap()),
        "{is-preferred=b:true,refresh-rate=d:30.000000,size=(uu):(1280,960)}"
    );
    // A zero rate omits the key so Mutter defaults it to 60.0.
    assert_eq!(
        gnome::canonical_dict(&gnome::virtual_monitor_mode(1280, 960, 0.0, true).unwrap()),
        "{is-preferred=b:true,size=(uu):(1280,960)}"
    );
    assert!(gnome::virtual_monitor_mode(0, 960, 30.0, true).is_err());
    assert!(gnome::virtual_monitor_mode(1280, 960, -1.0, true).is_err());
}

#[test]
fn record_virtual_defaults_to_a_pinned_mode_and_embedded_cursor() {
    let properties =
        gnome::record_virtual_properties(&[], gnome::CURSOR_MODE_EMBEDDED, None).unwrap();
    let text = gnome::canonical_dict(&properties);
    assert!(text.contains("cursor-mode=u:1"));
    assert!(text.contains("size=(uu):(1280,960)"));
    // is-platform stays absent unless asked for: setting it suppresses the
    // sharing indicator, which is the user's decision.
    assert!(!text.contains("is-platform"));
    assert!(gnome::record_virtual_properties(&[], 3, None).is_err());
}

#[test]
fn the_preferred_mode_count_is_enforced() {
    let none = vec![gnome::virtual_monitor_mode(1280, 960, 30.0, false).unwrap()];
    assert!(gnome::record_virtual_properties(&none, 1, None).is_err());
    let two = vec![
        gnome::observed_mode().unwrap(),
        gnome::virtual_monitor_mode(640, 480, 60.0, true).unwrap(),
    ];
    assert!(gnome::record_virtual_properties(&two, 1, None).is_err());
    let one = vec![
        gnome::observed_mode().unwrap(),
        gnome::virtual_monitor_mode(640, 480, 60.0, false).unwrap(),
    ];
    assert!(gnome::record_virtual_properties(&one, 1, None).is_ok());
}

#[test]
fn a_button_record_moves_before_it_presses() {
    // A tap arrives as a bare 5 -> 6 with no motion record first, so the
    // position has to be applied before the press or it lands wherever the
    // pointer happened to be.
    let plan = gnome::plan_injection(5, 100, 200, "/stream", 1280, 960).unwrap();
    assert_eq!(plan.len(), 2);
    assert_eq!(plan[0].method, "NotifyPointerMotionAbsolute");
    assert_eq!(plan[1].method, "NotifyPointerButton");
    assert_eq!(plan[1].args[0], gnome::PropValue::Int32(gnome::BTN_LEFT));
    assert_eq!(plan[1].args[1], gnome::PropValue::Bool(true));
    let up = gnome::plan_injection(6, 100, 200, "/stream", 1280, 960).unwrap();
    assert_eq!(up[1].args[1], gnome::PropValue::Bool(false));
}

#[test]
fn coordinates_pass_straight_through_as_doubles() {
    // Mutter adds the monitor's stage offset itself, so there is no transform
    // to reproduce — the Windows 65535 normalisation has no counterpart.
    let plan = gnome::plan_injection(10, 640, 480, "/stream", 1280, 960).unwrap();
    assert_eq!(plan.len(), 1);
    assert_eq!(plan[0].args[1], gnome::PropValue::Double(640.0));
    assert_eq!(plan[0].args[2], gnome::PropValue::Double(480.0));
}

#[test]
fn field0_values_with_no_pointer_meaning_plan_nothing() {
    for field0 in [1, 2, 3, 11, 12, 13, 16, 17] {
        assert!(
            gnome::plan_injection(field0, 10, 10, "/stream", 1280, 960)
                .unwrap()
                .is_empty(),
            "field0 {field0} should plan nothing"
        );
    }
}

#[test]
fn a_coordinate_outside_the_display_is_a_fault_not_clamped() {
    assert!(gnome::plan_injection(10, 1281, 0, "/stream", 1280, 960).is_err());
    assert!(gnome::plan_injection(10, 0, 961, "/stream", 1280, 960).is_err());
    assert!(gnome::plan_injection(10, -1, 0, "/stream", 1280, 960).is_err());
    // The far corner is inside, inclusively.
    assert!(!gnome::plan_injection(10, 1280, 960, "/stream", 1280, 960)
        .unwrap()
        .is_empty());
    // And the stream path is required: it is the 'stream' argument.
    assert!(gnome::plan_injection(10, 0, 0, "", 1280, 960).is_err());
}

#[test]
fn a_value_reports_its_signature() {
    assert_eq!(gnome::PropValue::UInt32(1).signature(), "u");
    assert_eq!(gnome::PropValue::Int32(1).signature(), "i");
    assert_eq!(gnome::PropValue::Size(1, 2).signature(), "(uu)");
    assert_eq!(gnome::PropValue::Double(1.0).signature(), "d");
}

// ---------------------------------------------------------------------------
// capture and pacing
// ---------------------------------------------------------------------------

#[test]
fn the_pipeline_pins_the_geometry_the_prelude_declares() {
    let description = capture::pipeline_description(7, 1280, 960, 30).unwrap();
    assert!(description.contains("pipewiresrc path=7"));
    assert!(description.contains("width=1280,height=960"));
    assert!(description.contains("format=RGB"));
    assert!(description.contains("videoconvert"));
    assert!(description.contains("max-buffers=1 drop=true"));
    assert!(description.contains("appsink name=sink"));
    // Node ids start at 0, so 0 is valid and negative is not.
    assert!(capture::pipeline_description(0, 1280, 960, 30).is_ok());
    assert!(capture::pipeline_description(-1, 1280, 960, 30).is_err());
    assert!(capture::pipeline_description(1, 0, 960, 30).is_err());
    assert!(capture::pipeline_description(1, 1280, 960, 0).is_err());
}

#[test]
fn a_frame_of_the_wrong_size_is_refused_not_resized() {
    assert!(capture::validate_frame_geometry(1280, 960, 1280, 960).is_ok());
    assert!(capture::validate_frame_geometry(1920, 1080, 1280, 960).is_err());
    // A scaled monitor is the likely cause, so a halved size must fail too
    // rather than look like a plausible frame.
    assert!(capture::validate_frame_geometry(640, 480, 1280, 960).is_err());
}

#[test]
fn the_pacer_schedules_against_the_target_not_the_wakeup() {
    let mut p = pacer::Pacer::new(30).unwrap();
    assert_eq!(p.interval_s(), 0.033);
    assert_eq!(p.sleep_s(0.0), 0.0); // schedules the target at 0.033
                                     // Woken 10 ms late, the next wait is shortened so the schedule holds.
    let second = p.sleep_s(0.010);
    assert!(second > 0.022 && second < 0.024, "got {second}");
}

#[test]
fn a_stall_longer_than_an_interval_resets_instead_of_bursting() {
    // Catching up would mean a burst of 30 frames, so the schedule restarts.
    let mut p = pacer::Pacer::new(30).unwrap();
    assert_eq!(p.sleep_s(0.0), 0.0);
    assert_eq!(p.sleep_s(1.0), 0.0);
    // And a wait is never negative.
    for now in [5.0, 10.0, 20.0] {
        assert!(p.sleep_s(now) >= 0.0);
    }
}
