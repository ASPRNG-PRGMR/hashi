//! Emits the Rust core's wire bytes as `name hex` lines, for
//! `native/tools/conformance.py` to diff against the Python reference and the
//! C++ port.
//!
//! The point is not that three implementations pass similar tests, but that
//! they produce the same bytes. The Python side is the reference: it is what
//! reproduced the captured 130,375,177-byte stream byte-for-byte and what
//! drove the device in FED-LIVE-E001 and FED-HOST-E001.
//!
//! Every vector here is pure computation. Nothing in this binary opens a
//! socket, a bus or a pipeline.

use hashi::{capture, gnome, jpeg, pacer, startup, stream, usbmux};

fn emit(name: &str, bytes: &[u8]) {
    let hex: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
    println!("{name} {hex}");
}

fn emit_text(name: &str, text: &str) {
    println!("{name} {text}");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // --- startup ----------------------------------------------------------
    emit("probe", &startup::encode_byte_order_probe());
    emit("hello", &startup::control(startup::MSG_HELLO)?);
    emit("ready", &startup::control(startup::MSG_READY)?);
    // The 0xfc record's field1 carries no byte swap. Reproduced, not fixed.
    emit(
        "extra_request",
        &startup::encode_control(startup::MSG_EXTRA_REQUEST, 5, 0, true, true)?,
    );
    emit(
        "hello_ack_2048x1536",
        &startup::encode_control(startup::MSG_HELLO_ACK, 2048, 1536, true, false)?,
    );
    emit("ready_ack", &startup::control(startup::MSG_READY_ACK)?);
    emit(
        "legacy_hello",
        &startup::encode_control(startup::MSG_HELLO, 0, 0, false, false)?,
    );
    emit("header_5_12", &startup::encode_header(5, 12)?);
    emit("header_6_19827", &startup::encode_header(6, 19827)?);
    emit("header_6_max", &startup::encode_header(6, 0xFF_FFFF)?);

    // --- stream -----------------------------------------------------------
    emit(
        "image_record_small",
        &stream::encode_image_record(&[0xFF, 0xD8, 0xFF, 0xD9])?,
    );
    {
        let payload = vec![0xABu8; 1000];
        let mut record = stream::encode_image_record(&payload)?;
        record.truncate(8); // the header plus a few bytes is enough for framing
        emit("image_record_1000_head", &record);
    }

    // --- JPEG frame prelude -----------------------------------------------
    emit("jpeg_app0", &jpeg::build_app0(jpeg::OBSERVED_DENSITY)?);
    emit("jpeg_app0_density_72", &jpeg::build_app0(72)?);
    emit(
        "jpeg_dqt_luma_q80",
        &jpeg::build_dqt(&jpeg::BASE_LUMA_QTABLE, 0, 80)?,
    );
    emit(
        "jpeg_dqt_chroma_q80",
        &jpeg::build_dqt(&jpeg::BASE_CHROMA_QTABLE, 1, 80)?,
    );
    // Below 50 the IJG formula switches branch, and 100 is the clamp boundary.
    emit(
        "jpeg_dqt_luma_q25",
        &jpeg::build_dqt(&jpeg::BASE_LUMA_QTABLE, 0, 25)?,
    );
    emit(
        "jpeg_dqt_luma_q100",
        &jpeg::build_dqt(&jpeg::BASE_LUMA_QTABLE, 0, 100)?,
    );
    emit(
        "jpeg_dqt_luma_q1",
        &jpeg::build_dqt(&jpeg::BASE_LUMA_QTABLE, 0, 1)?,
    );
    emit("jpeg_sof0_1280x960", &jpeg::build_sof0(1280, 960)?);
    emit("jpeg_sof0_odd", &jpeg::build_sof0(17, 5)?);
    emit(
        "jpeg_dht_dc_luma",
        &jpeg::build_dht(0, 0, &jpeg::DC_LUMA_COUNTS, &jpeg::DC_LUMA_VALUES)?,
    );
    emit(
        "jpeg_dht_ac_luma",
        &jpeg::build_dht(1, 0, &jpeg::AC_LUMA_COUNTS, &jpeg::AC_LUMA_VALUES)?,
    );
    emit(
        "jpeg_dht_dc_chroma",
        &jpeg::build_dht(0, 1, &jpeg::DC_CHROMA_COUNTS, &jpeg::DC_CHROMA_VALUES)?,
    );
    emit(
        "jpeg_dht_ac_chroma",
        &jpeg::build_dht(1, 1, &jpeg::AC_CHROMA_COUNTS, &jpeg::AC_CHROMA_VALUES)?,
    );
    emit("jpeg_sos", &jpeg::build_sos());
    emit("jpeg_prelude_observed", &jpeg::observed_prelude()?);
    emit("jpeg_prelude_odd", &jpeg::build_prelude(17, 5, 25, 72)?);

    // --- Mutter D-Bus arguments and injection plans -----------------------
    // Compared as a canonical text form: GLib builds the actual message, so
    // what matters is that the implementations decide on the same signatures,
    // keys, defaults and values.
    {
        let stream_path = "/org/gnome/Mutter/ScreenCast/Stream/u0";

        emit_text(
            "gnome_mode_default",
            &gnome::canonical_dict(&gnome::observed_mode()?),
        );
        emit_text(
            "gnome_mode_no_refresh",
            &gnome::canonical_dict(&gnome::virtual_monitor_mode(1280, 960, 0.0, true)?),
        );
        emit_text(
            "gnome_mode_custom",
            &gnome::canonical_dict(&gnome::virtual_monitor_mode(640, 480, 59.94, false)?),
        );

        emit_text(
            "gnome_record_virtual_default",
            &gnome::canonical_dict(&gnome::record_virtual_properties(
                &[],
                gnome::CURSOR_MODE_EMBEDDED,
                None,
            )?),
        );
        emit_text(
            "gnome_record_virtual_cursor_hidden",
            &gnome::canonical_dict(&gnome::record_virtual_properties(
                &[],
                gnome::CURSOR_MODE_HIDDEN,
                None,
            )?),
        );
        emit_text(
            "gnome_record_virtual_platform_true",
            &gnome::canonical_dict(&gnome::record_virtual_properties(
                &[],
                gnome::CURSOR_MODE_EMBEDDED,
                Some(true),
            )?),
        );
        emit_text(
            "gnome_record_virtual_platform_false",
            &gnome::canonical_dict(&gnome::record_virtual_properties(
                &[],
                gnome::CURSOR_MODE_EMBEDDED,
                Some(false),
            )?),
        );

        emit_text(
            "gnome_session_props_empty",
            &gnome::canonical_dict(&gnome::screen_cast_session_properties("", None)),
        );
        emit_text(
            "gnome_session_props_id",
            &gnome::canonical_dict(&gnome::screen_cast_session_properties("17", None)),
        );
        emit_text(
            "gnome_session_props_both",
            &gnome::canonical_dict(&gnome::screen_cast_session_properties("17", Some(true))),
        );

        let plan =
            |name: &str, field0: i32, x: i32, y: i32| -> Result<(), Box<dyn std::error::Error>> {
                let calls = gnome::plan_injection(
                    field0,
                    x,
                    y,
                    stream_path,
                    gnome::TARGET_WIDTH,
                    gnome::TARGET_HEIGHT,
                )?;
                emit_text(name, &gnome::canonical_plan(&calls));
                Ok(())
            };
        plan("gnome_inject_down", 5, 100, 200)?;
        plan("gnome_inject_up", 6, 100, 200)?;
        plan("gnome_inject_motion", 10, 640, 480)?;
        plan("gnome_inject_right_down", 8, 1, 2)?;
        plan("gnome_inject_right_up", 9, 1, 2)?;
        plan("gnome_inject_middle_down", 14, 3, 4)?;
        plan("gnome_inject_middle_up", 15, 3, 4)?;
        plan("gnome_inject_move_only_4", 4, 5, 6)?;
        plan("gnome_inject_move_only_7", 7, 5, 6)?;
        // Origin and the far corner: both are inside the display, inclusively.
        plan("gnome_inject_origin", 10, 0, 0)?;
        plan("gnome_inject_corner", 10, 1280, 960)?;
        // Values with no pointer meaning must plan nothing at all.
        plan("gnome_inject_keyboard_1", 1, 10, 10)?;
        plan("gnome_inject_keyboard_2", 2, 10, 10)?;
        plan("gnome_inject_control_16", 16, 10, 10)?;
        plan("gnome_inject_control_17", 17, 10, 10)?;
        plan("gnome_inject_unseen_11", 11, 10, 10)?;
    }

    // --- Capture pipeline -------------------------------------------------
    emit_text(
        "pipeline_default",
        &capture::pipeline_description(42, 1280, 960, 30)?,
    );
    emit_text(
        "pipeline_custom",
        &capture::pipeline_description(0, 640, 480, 60)?,
    );

    // --- Frame pacing -----------------------------------------------------
    // A scripted clock, so the schedule arithmetic is what is compared rather
    // than wall-clock behaviour.
    {
        let script = [0.0, 0.010, 0.033, 0.040, 1.0, 1.0, 1.033, 1.040];
        for fps in [30, 60] {
            let mut p = pacer::Pacer::new(fps)?;
            let values: Vec<String> = script
                .iter()
                .map(|&now| format!("{:.6}", p.sleep_s(now)))
                .collect();
            emit_text(&format!("pacer_schedule_{fps}"), &values.join(","));
        }
    }

    // --- usbmux header framing -------------------------------------------
    // The plist body itself is not compared: usbmuxd parses XML, and the three
    // writers legitimately differ in whitespace. The header is what the
    // protocol pins, so that is what is checked, with the body length removed.
    {
        let connect = usbmux::build_connect(1, usbmux::APPLICATION_PORT, 14, None)?;
        emit("connect_header_tail", &connect[4..16]);
    }
    println!(
        "port_swapped {}",
        usbmux::htons_port(usbmux::APPLICATION_PORT)?
    );
    println!("align_2048 {}", startup::align_client_dimension(2048));
    println!("align_1 {}", startup::align_client_dimension(1));
    println!("align_5 {}", startup::align_client_dimension(5));
    println!("interval_30 {}", stream::frame_interval_ms(30)?);
    println!("interval_60 {}", stream::frame_interval_ms(60)?);
    Ok(())
}
