#!/usr/bin/env python3
"""Command-line entry point for the Python host.

The Python modules are the implementation that has actually driven the device
(FED-HOST-E001, 2026-11-08): the iPad displayed frames generated from a Mutter
virtual monitor and touches moved the Linux pointer. Until now they were a
library with no way to start them — the live run was driven by an ad-hoc script
kept outside the repository with the rest of the instrumentation. This is that
startup sequence as a supported entry point.

**The ordering below is the whole point of this file.** Capture must be running
and a first frame pulled *before* any input is injected, because Mutter
silently discards absolute pointer motion until something consumes the PipeWire
stream — while still returning success on the D-Bus call. Buttons land anyway,
so getting this wrong does not produce an error: it produces clicks at a stale
position, selected text and windows behaving oddly, with a cursor that never
moves. Measured with Mutter's idle timer: 40 motion calls left idle climbing
14,741 -> 15,605 ms with no consumer, and took it 20,683 -> 21 ms with one.

Two of the three commands are inert. ``plan`` prints what a run would do and
touches nothing; ``devices`` asks the local usbmuxd what is attached, which
talks to the daemon and not to the iPad. Only ``run`` streams, and it needs
``--allow-session`` because it has effects the user must choose: a monitor
appears on the desktop, a screen-sharing indicator shows, and bytes go to the
device.
"""

from __future__ import annotations

import argparse
import json
import signal
import socket
import sys
import time

import hashi_gnome as gnome
import hashi_host as host
import hashi_jpeg as jpeg
import hashi_stream as stream
import hashi_usbmux as usbmux

#: Frames per ``run()`` call.
#:
#: The loop is batched so progress can be printed and Ctrl-C can be honoured at
#: a boundary, which means the host's pacer is rebuilt once per batch and its
#: first frame of each batch does not wait. At 30 frames that overshoots the
#: target rate by about 3%. It is stated rather than hidden; the stream is
#: wire-bound and damage-driven, so exact pacing is not what limits it.
BATCH_FRAMES = 30

_interrupted = False


def _on_interrupt(_signum, _frame) -> None:
    global _interrupted
    _interrupted = True
    print("\ninterrupted; finishing this batch and tearing down", flush=True)


# ---------------------------------------------------------------------------
# usbmux device listing
# ---------------------------------------------------------------------------


def _recv_usbmux_message(sock: socket.socket) -> bytes:
    """Read one complete usbmux message: its 16-byte header, then its body."""
    header = b""
    while len(header) < usbmux.USBMUX_HEADER_LEN:
        chunk = sock.recv(usbmux.USBMUX_HEADER_LEN - len(header))
        if not chunk:
            raise host.HostError("usbmuxd closed the connection mid-header")
        header += chunk
    # decode_header raises UsbmuxError on a length shorter than the header,
    # so there is no second check here to drift out of step with it.
    length = usbmux.decode_header(header)[0]
    body = b""
    while len(body) < length - usbmux.USBMUX_HEADER_LEN:
        chunk = sock.recv(length - usbmux.USBMUX_HEADER_LEN - len(body))
        if not chunk:
            raise host.HostError("usbmuxd closed the connection mid-body")
        body += chunk
    return header + body


def list_devices() -> list[dict]:
    """Ask usbmuxd what is attached. Reaches the daemon, not the device."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(usbmux.LINUX_USBMUXD_SOCKET)
    except OSError as exc:
        raise host.HostError(
            f"cannot reach usbmuxd at {usbmux.LINUX_USBMUXD_SOCKET}: {exc}. "
            "Is usbmuxd running?"
        ) from exc
    try:
        sock.sendall(usbmux.build_list_devices())
        _, listing = usbmux.decode_message(_recv_usbmux_message(sock))
        return usbmux.parse_device_list(listing)
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def command_plan(args: argparse.Namespace) -> int:
    print("A run with this configuration would:")
    print(f"  - connect to usbmuxd at {usbmux.LINUX_USBMUXD_SOCKET}")
    if args.device_id is None:
        print("  - discover the device id with ListDevices, selecting product "
              f"id 0x{usbmux.IPAD_PRODUCT_ID:04x}")
        print("    (usbmuxd reassigns the id on every attach, so discovery is "
              "the right default)")
    else:
        print(f"  - use device id {args.device_id} without discovery")
    print(f"  - Connect to port {usbmux.APPLICATION_PORT}, carried as "
          f"{usbmux.htons_port(usbmux.APPLICATION_PORT)} byte-swapped")
    print("  - complete the handshake: byte-order probe, HELLO, READY, "
          "extra-data request")
    if args.solid:
        print(f"  - stream alternating solid {jpeg.OBSERVED_WIDTH}x"
              f"{jpeg.OBSERVED_HEIGHT} frames; NO virtual monitor and NO "
              "injection")
        print("    (the black frame is byte-identical to the captured stream's "
              "first record, so this separates a transport fault from a "
              "capture one)")
    else:
        print(f"  - create a Mutter virtual monitor pinned to "
              f"{gnome.TARGET_WIDTH}x{gnome.TARGET_HEIGHT} at "
              f"{args.refresh:.1f} Hz, cursor embedded in the frames")
        print("  - capture it over PipeWire with:")
        print(f"      {host.capture_pipeline_description(0, fps=args.fps)}")
        print("  - pull a first frame BEFORE injecting anything, so the stream "
              "has a consumer")
        print("  - inject inbound type-7 records as pointer events")
    print(f"  - pace to {args.fps} fps, an interval of "
          f"{stream.frame_interval_ms(args.fps)} ms")
    if args.skip_unchanged:
        print("  - skip frames identical to the last one sent, but re-send one "
              f"every {args.keepalive:.1f}s regardless, because what the device "
              "does with a silent stream has never been observed")
    else:
        print("  - re-send every frame, identical or not")
    if args.seconds:
        print(f"  - stop after {args.seconds}s")
    else:
        print("  - run until interrupted with Ctrl-C")
    print("\nNothing was done. Add --allow-session to `run` to do it.")
    return 0


def command_devices(_args: argparse.Namespace) -> int:
    devices = list_devices()
    if not devices:
        print("usbmuxd reports no attached devices.")
        return 1
    for device in devices:
        product = device.get("product_id", 0)
        marker = "  <- iPad" if product == usbmux.IPAD_PRODUCT_ID else ""
        print(f"device id {device.get('device_id')}  "
              f"product 0x{product:04x}  "
              f"{device.get('connection_type', '?')}  "
              f"{device.get('serial', '')}{marker}")
    return 0


def _print_stats(session: host.HostSession, source) -> None:
    stats = session.stats
    line = (f"  frames sent {stats.frames_sent} skipped {stats.frames_skipped} "
            f"({stats.bytes_sent / 1e6:.1f} MB)  "
            f"records {stats.records_received} injected {stats.events_injected}")
    if stats.records_dropped_no_consumer:
        line += f" DROPPED-NO-CONSUMER {stats.records_dropped_no_consumer}"
    if isinstance(source, host.PipeWireFrameSource):
        line += f"  captured {source.frames_captured} repeated {source.frames_repeated}"
    print(line, flush=True)


def command_run(args: argparse.Namespace) -> int:
    if not args.allow_session:
        effects = "It sends bytes to the iPad"
        if not args.solid:
            effects += (" and creates a Mutter session, which puts a monitor on "
                        "your desktop and raises a screen-sharing indicator")
        print(f"hashi: `run` needs --allow-session.\n{effects}.\n"
              "Use `plan` to see exactly what it would do.", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _on_interrupt)

    display = None
    source = None
    session = None
    try:
        # --- 1. the virtual monitor -----------------------------------------
        # Pinned via RecordVirtual's `modes`, which also makes the PipeWire
        # stream non-resizable. The JPEG prelude hard-codes 1280x960, so a
        # pinned mode turns a whole class of size mismatch into an
        # impossibility rather than a case to handle.
        if args.solid:
            source = host.SolidColourSource(hold_frames=max(args.fps // 2, 1))
            print("solid-colour source: no virtual monitor, no injection",
                  flush=True)
        else:
            display = gnome.VirtualDisplaySession(
                width=gnome.TARGET_WIDTH,
                height=gnome.TARGET_HEIGHT,
                refresh_rate=args.refresh,
                cursor_mode=gnome.CURSOR_MODE_EMBEDDED,
            )
            node_id = display.open()
            print(f"virtual monitor up; PipeWire node {node_id}", flush=True)

            # --- 2. capture, and a first frame BEFORE anything is injected ---
            # This is the ordering the file's docstring is about. Pulling a
            # frame proves a consumer is attached; without it every absolute
            # motion would be discarded while the D-Bus call still succeeded.
            source = host.PipeWireFrameSource(node_id, fps=args.fps)
            source.start()
            source.next_payload()
            print("capture live, first frame pulled: the stream has a consumer",
                  flush=True)

        # --- 3. the handshake ------------------------------------------------
        session = host.HostSession(
            device_id=args.device_id,
            fps=args.fps,
            source=source,
            display=display,
            inject=not args.solid,
            skip_unchanged=args.skip_unchanged,
            keepalive_interval_s=args.keepalive,
        )
        dimensions = session.connect()
        print(f"handshake complete; device reports {dimensions[0]}x"
              f"{dimensions[1]}, diff_jpeg={session.diff_jpeg}", flush=True)
        if display is not None:
            print("STREAMING -- drag a window onto the new monitor, and touch "
                  "the iPad to move the pointer", flush=True)
        else:
            print("STREAMING -- the iPad should flash black and white",
                  flush=True)

        # --- 4. the loop -----------------------------------------------------
        deadline = time.monotonic() + args.seconds if args.seconds else None
        last_report = time.monotonic()
        while not _interrupted:
            if deadline is not None and time.monotonic() >= deadline:
                break
            session.run(frames=BATCH_FRAMES)
            if time.monotonic() - last_report >= 2.0:
                _print_stats(session, source)
                last_report = time.monotonic()
        return 0

    except (host.HostError, gnome.GnomeError, usbmux.UsbmuxError) as error:
        print(f"hashi: {error}", file=sys.stderr)
        return 1
    finally:
        # Teardown must not mask whatever brought us here, so each step is
        # attempted and its failure reported rather than raised.
        print()
        if session is not None:
            _print_stats(session, source)
            stats = session.stats
            print(json.dumps({
                "frames_sent": stats.frames_sent,
                "frames_skipped": stats.frames_skipped,
                "bytes_sent": stats.bytes_sent,
                "records_received": stats.records_received,
                "events_injected": stats.events_injected,
                "records_ignored": stats.records_ignored,
                "records_dropped_no_consumer":
                    stats.records_dropped_no_consumer,
            }, indent=2))
            try:
                session.close()   # also closes the frame source
            except Exception as exc:  # noqa: BLE001 - best effort
                print(f"hashi: teardown: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
        elif source is not None:
            try:
                source.close()
            except Exception as exc:  # noqa: BLE001
                print(f"hashi: teardown: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
        if display is not None:
            # Stopping the remote-desktop session stops the cast with it, so
            # close() does not stop both; it returns what it swallowed.
            for error in display.close():
                print(f"hashi: teardown: {error}", file=sys.stderr)


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hashi_cli.py",
        description="A Linux host for the unmodified Splashtop Wired XDisplay "
                    "iPad app.",
        epilog="`plan` and `devices` touch no device. `run` needs "
               "--allow-session.",
    )
    parser.add_argument("command", choices=("plan", "devices", "run"),
                        help="plan: print what a run would do. devices: ask "
                             "usbmuxd what is attached. run: stream.")
    parser.add_argument("--allow-session", action="store_true",
                        help="permit contacting the device and creating a "
                             "Mutter session")
    parser.add_argument("--solid", action="store_true",
                        help="stream solid frames instead of capturing: no "
                             "virtual monitor and no injection. Separates a "
                             "transport fault from a capture one.")
    parser.add_argument("--fps", type=int, default=host.TARGET_FPS,
                        help=f"target frame rate (default {host.TARGET_FPS})")
    parser.add_argument("--refresh", type=float, default=gnome.TARGET_REFRESH,
                        help="virtual monitor refresh rate in Hz (default "
                             f"{gnome.TARGET_REFRESH})")
    parser.add_argument("--device-id", type=int, default=None,
                        help="skip discovery and use this usbmux device id. "
                             "Discovery is normally right: usbmuxd reassigns "
                             "the id on every attach.")
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="stop after this many seconds (default: until "
                             "Ctrl-C)")
    parser.add_argument("--no-skip-unchanged", dest="skip_unchanged",
                        action="store_false",
                        help="re-send every frame, even ones identical to the "
                             "last")
    parser.add_argument("--keepalive", type=float, default=1.0,
                        help="seconds between re-sends of an unchanged frame "
                             "(default 1.0)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fps <= 0:
        print("hashi: --fps must be positive", file=sys.stderr)
        return 2
    if args.keepalive <= 0:
        print("hashi: --keepalive must be positive", file=sys.stderr)
        return 2
    try:
        if args.command == "plan":
            return command_plan(args)
        if args.command == "devices":
            return command_devices(args)
        return command_run(args)
    except (host.HostError, gnome.GnomeError, usbmux.UsbmuxError) as error:
        # Every layer has its own error type; a user reading the terminal
        # should not have to care which one surfaced.
        print(f"hashi: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
