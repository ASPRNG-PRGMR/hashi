"""The HASHI host: wires the decoded protocol to the GNOME display and input.

Every layer below this one is already built and validated on its own:

* :mod:`hashi_usbmux` — the transport, validated against the captured control
  exchange and used live in FED-LIVE-E001;
* :mod:`hashi_startup` — the handshake, byte-exact offline and successful
  against the real device first time;
* :mod:`hashi_stream` — the record codec and the decoded input semantics, with
  the whole outbound direction reproducing byte-for-byte;
* :mod:`hashi_jpeg` — frame encoding, byte-identical to the agent's encoder for
  the one frame whose source pixels could be reconstructed;
* :mod:`hashi_gnome` — the virtual monitor and input injection, against D-Bus
  contracts verified as FED-DBUS-E001.

This module is the part that had never been written: the loop that turns a
captured desktop into frames on the wire and inbound records into pointer
events. **It has never been run.** That matters more here than anywhere else in
the project, because unlike the layers beneath it there is no capture to check
it against — the composition is a design **Inference** throughout.

The split is deliberate: everything that can be tested without a compositor, a
device or a socket is a pure function or an injectable object, and the live
parts (:class:`PipeWireFrameSource`, :class:`HostSession`) are thin shells over
them. :class:`InboundDemuxer` in particular is pure, because stream reassembly
is where a framing bug would hide and the 1,449 observed records give something
concrete to test it against.

Nothing here opens a socket, creates a D-Bus session or contacts the iPad until
a method is called. Importing it does nothing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import hashi_gnome as gnome
import hashi_jpeg as jpeg
import hashi_startup as startup
import hashi_stream as stream
import hashi_usbmux as usbmux

__all__ = [
    "HostError",
    "TARGET_WIDTH",
    "TARGET_HEIGHT",
    "TARGET_FPS",
    "capture_pipeline_description",
    "validate_frame_geometry",
    "FrameSource",
    "SolidColourSource",
    "ReplayFrameSource",
    "PipeWireFrameSource",
    "InboundDemuxer",
    "Pacer",
    "HostSession",
]

TARGET_WIDTH = gnome.TARGET_WIDTH
TARGET_HEIGHT = gnome.TARGET_HEIGHT

#: 30 fps, the rate the FED-LIVE-E001 replay ran at and the rate the pinned
#: virtual-monitor mode declares.
TARGET_FPS = 30


class HostError(RuntimeError):
    """The host's own composition failed — not a protocol or contract fault."""


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def capture_pipeline_description(
    node_id: int,
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = TARGET_FPS,
) -> str:
    """The GStreamer pipeline that turns a PipeWire node into RGB frames.

    ``node_id`` is what ``Stream.PipeWireStreamAdded`` hands back; it is the
    ``path`` property of ``pipewiresrc`` (verified present on the installed
    element, along with ``fd``).

    The caps are pinned to the same geometry as the virtual monitor's mode, so a
    mismatch fails in negotiation rather than silently producing frames of the
    wrong size — which would matter, because the JPEG prelude hard-codes
    1280x960.

    ``videoconvert`` is unconditional: the compositor's buffers are typically
    BGRx or BGRA, and Pillow needs RGB. ``max-buffers=1 drop=true`` on the sink
    keeps the loop on the newest frame rather than accumulating latency, which
    suits a display far more than completeness would.
    """
    if node_id < 0:
        raise HostError(f"node_id must be non-negative, got {node_id}")
    if width <= 0 or height <= 0:
        raise HostError(f"invalid geometry {width}x{height}")
    if fps <= 0:
        raise HostError(f"fps must be positive, got {fps}")
    return (
        f"pipewiresrc path={node_id} always-copy=true ! "
        f"videoconvert ! "
        f"video/x-raw,format=RGB,width={width},height={height} ! "
        f"appsink name=sink emit-signals=false max-buffers=1 drop=true "
        f"sync=false"
    )


def validate_frame_geometry(
    width: int, height: int, *, expected: tuple[int, int] | None = None
) -> None:
    """Refuse a frame whose size does not match the protocol's declared size.

    FED-JPEG-E001's 623-byte prelude encodes 1280x960 in its SOF0, so a frame of
    any other size would be a JPEG whose dimensions disagree with the stream the
    device was told to expect. Fail loudly rather than send it.
    """
    want = expected or (TARGET_WIDTH, TARGET_HEIGHT)
    if (width, height) != want:
        raise HostError(
            f"captured frame is {width}x{height}, expected {want[0]}x{want[1]}; "
            "the JPEG prelude hard-codes the expected size, so this frame "
            "cannot be sent. Check the virtual monitor's pinned mode and "
            "whether the compositor applied a scale."
        )


class FrameSource:
    """Supplies encoded JPEG frame payloads.

    Subclassed rather than duck-typed so the live and offline sources are
    interchangeable in :class:`HostSession`, which is what makes the session
    testable without a compositor.
    """

    def next_payload(self) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        return None


class SolidColourSource(FrameSource):
    """Emits solid-colour frames. The known-good source.

    This is the one frame-generation path with byte-exact validation behind it:
    a generated solid black 1280x960 frame is byte-identical to the first
    captured record, scan data included. So if a live run shows nothing on the
    iPad, this source distinguishes a frame-generation fault from a capture or
    transport fault.
    """

    def __init__(
        self,
        colours=((0, 0, 0), (255, 255, 255)),
        *,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        hold_frames: int = 1,
    ) -> None:
        if not colours:
            raise HostError("at least one colour is required")
        if hold_frames < 1:
            raise HostError(f"hold_frames must be >= 1, got {hold_frames}")
        self.colours = list(colours)
        self.width = width
        self.height = height
        self.hold_frames = hold_frames
        self._index = 0
        self._cache: dict[tuple[int, int, int], bytes] = {}

    def next_payload(self) -> bytes:
        colour = self.colours[(self._index // self.hold_frames) % len(self.colours)]
        self._index += 1
        if colour not in self._cache:
            self._cache[colour] = jpeg.solid_frame(self.width, self.height, colour)
        return self._cache[colour]


class ReplayFrameSource(FrameSource):
    """Replays pre-encoded payloads. What FED-LIVE-E001 actually streamed.

    Kept because it is the only source already proven to put a recognisable
    picture on the iPad, which makes it the reference when a generated frame
    does not.
    """

    def __init__(self, payloads, *, loop: bool = True) -> None:
        self.payloads = list(payloads)
        if not self.payloads:
            raise HostError("no payloads to replay")
        self.loop = loop
        self._index = 0

    def next_payload(self) -> bytes:
        if self._index >= len(self.payloads):
            if not self.loop:
                raise StopIteration("replay exhausted")
            self._index = 0
        payload = self.payloads[self._index]
        self._index += 1
        return payload


class PipeWireFrameSource(FrameSource):
    """Captures the virtual monitor over PipeWire and encodes each frame.

    **Never executed.** GStreamer is imported lazily, so merely constructing a
    :class:`HostSession` with a different source costs nothing.
    """

    def __init__(
        self,
        node_id: int,
        *,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        fps: int = TARGET_FPS,
        timeout_s: float = 5.0,
        poll_timeout_s: float | None = None,
    ) -> None:
        self.node_id = node_id
        self.width = width
        self.height = height
        self.fps = fps
        #: How long to wait for the *first* frame, i.e. for the stream to start.
        self.timeout_s = timeout_s
        #: How long to wait for each later frame before repeating the last one.
        #: Defaults to one frame interval, so a static screen paces normally.
        self.poll_timeout_s = (
            poll_timeout_s if poll_timeout_s is not None else 1.0 / max(fps, 1)
        )
        self.frames_captured = 0
        self.frames_repeated = 0
        self._last_payload: bytes | None = None
        self._pipeline = None
        self._sink = None

    def start(self) -> None:
        import gi  # noqa: PLC0415

        gi.require_version("Gst", "1.0")
        gi.require_version("GstApp", "1.0")
        # GstApp must be imported even though it is not referenced: appsink's
        # pull methods live in that namespace, and without it the element is a
        # bare GstAppSink with no try_pull_sample.
        from gi.repository import Gst, GstApp  # noqa: PLC0415, F401

        if not Gst.is_initialized():
            Gst.init(None)
        description = capture_pipeline_description(
            self.node_id, self.width, self.height, self.fps
        )
        self._pipeline = Gst.parse_launch(description)
        self._sink = self._pipeline.get_by_name("sink")
        if self._sink is None:
            raise HostError("the capture pipeline has no appsink named 'sink'")
        if self._pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise HostError(
                "the capture pipeline refused to start; the PipeWire node may "
                "have gone away, or the pinned caps may not match the stream"
            )

    def next_payload(self) -> bytes:
        from PIL import Image  # noqa: PLC0415
        from gi.repository import Gst  # noqa: PLC0415

        if self._sink is None:
            raise HostError("capture not started; call start() first")

        # **Observed 2026-11-08:** the stream negotiates
        # ``framerate=(fraction)0/1`` with ``max-framerate=30/1``, i.e. variable
        # rate — Mutter produces a buffer only when the screen is *damaged*. An
        # idle desktop therefore yields no buffers at all, which is correct for
        # a screen cast and wrong for a display: the iPad still needs frames.
        #
        # So a timeout after the stream is running is not an error; it means
        # "nothing changed", and the right answer is to re-send the last frame.
        # Only never having received a frame is a genuine failure.
        first = self._last_payload is None
        timeout = self.timeout_s if first else self.poll_timeout_s
        sample = self._sink.try_pull_sample(int(timeout * Gst.SECOND))
        if sample is None:
            if first:
                raise HostError(
                    f"no first frame within {self.timeout_s}s; the stream never "
                    "started. Check that the PipeWire node still exists and "
                    "that the session was started."
                )
            self.frames_repeated += 1
            return self._last_payload

        caps = sample.get_caps().get_structure(0)
        width = caps.get_value("width")
        height = caps.get_value("height")
        validate_frame_geometry(width, height, expected=(self.width, self.height))

        buffer = sample.get_buffer()
        ok, info = buffer.map(Gst.MapFlags.READ)
        if not ok:
            raise HostError("could not map the captured buffer")
        try:
            # GStreamer pads each row up to a 4-byte boundary, so a buffer is
            # only densely packed when width * 3 is already a multiple of 4.
            # It is for 1280 (3840 bytes), but asserting it beats assuming it:
            # an unnoticed stride would shear the image diagonally rather than
            # fail, which is exactly the kind of fault that wastes a debugging
            # session on the protocol instead of the capture.
            expected = width * height * 3
            if info.size != expected:
                raise HostError(
                    f"captured buffer is {info.size} bytes for {width}x{height} "
                    f"RGB, expected {expected}. The rows are padded to a "
                    f"stride of {info.size // height} bytes, which this "
                    "unpacking does not handle."
                )
            image = Image.frombytes("RGB", (width, height), bytes(info.data))
        finally:
            buffer.unmap(info)
        payload = jpeg.encode_frame(image)
        self._last_payload = payload
        self.frames_captured += 1
        return payload

    def close(self) -> None:
        if self._pipeline is not None:
            from gi.repository import Gst  # noqa: PLC0415

            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
            self._sink = None


# ---------------------------------------------------------------------------
# Inbound reassembly
# ---------------------------------------------------------------------------


class InboundDemuxer:
    """Reassembles inbound TLV records from a byte stream.

    A socket hands over arbitrary chunks, so records arrive split and coalesced.
    This buffers bytes and yields whole records, using the decoded framing: a
    4-byte header of ``[type, BE24 length]`` followed by that many payload
    bytes.

    **Fact (FED-LIVE-E001):** every one of the 1,449 observed records was TLV
    type 7 with header ``07 00 00 0c`` and a 12-byte payload — 16 bytes total,
    with zero truncation. So the common path is a fixed 16-byte record, but the
    framing is honoured in general because the decode says the length is a
    field, not a constant.

    Parsing is delegated to :func:`hashi_stream.parse_tlv_record`, which clamps
    the payload to 12 bytes as the agent does. A longer record is consumed in
    full and reported truncated rather than desynchronising the stream — the
    bug this class exists to prevent.
    """

    HEADER_LEN = 4

    #: Refuse an absurd announced length rather than buffer unboundedly. The
    #: agent clamps what it *keeps* to 12 bytes but still consumes what was
    #: announced, so a hostile or corrupt length would otherwise stall the loop.
    MAX_PAYLOAD = 4096

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.records_seen = 0
        self.bytes_seen = 0

    def feed(self, data: bytes) -> list[stream.TlvRecord]:
        """Add bytes and return every complete record now available."""
        self._buffer.extend(data)
        self.bytes_seen += len(data)
        records: list[stream.TlvRecord] = []
        while True:
            if len(self._buffer) < self.HEADER_LEN:
                break
            header = bytes(self._buffer[: self.HEADER_LEN])
            _, announced = startup.decode_header(header)
            if announced == 0:
                raise stream.StreamError(
                    "TLV record announces a zero-length payload"
                )
            if announced > self.MAX_PAYLOAD:
                raise stream.StreamError(
                    f"TLV record announces {announced} payload bytes, above the "
                    f"{self.MAX_PAYLOAD}-byte sanity limit; the stream is "
                    "probably desynchronised"
                )
            total = self.HEADER_LEN + announced
            if len(self._buffer) < total:
                break
            payload = bytes(self._buffer[self.HEADER_LEN: total])
            del self._buffer[:total]
            records.append(stream.parse_tlv_record(header, payload))
            self.records_seen += 1
        return records

    @property
    def pending_bytes(self) -> int:
        """Bytes buffered but not yet a whole record."""
        return len(self._buffer)


# ---------------------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------------------


class Pacer:
    """Paces the outbound frame loop to a target rate.

    **A deliberate divergence from the agent, stated as such.** The decoded
    pacing reads only ``GetSystemTime``'s ``wMilliseconds``, so its own elapsed
    measurement wraps every second and cannot tell a 1.2-second stall from a
    200 ms one (:func:`hashi_stream.pacing_sleep_ms` reproduces that faithfully,
    including the wrap). A host has no reason to inherit that: this uses a
    monotonic clock instead.

    :func:`hashi_stream.frame_interval_ms` still supplies the target, so the
    interval and its truncation are the decoded ones.
    """

    def __init__(self, fps: int = TARGET_FPS, *, now=time.monotonic) -> None:
        self.interval_s = stream.frame_interval_ms(fps) / 1000.0
        self._now = now
        self._next: float | None = None

    def sleep_s(self) -> float:
        """Seconds to wait before the next frame. Never negative.

        Schedules against the previous *target* rather than the previous wakeup,
        so a late frame does not push every later frame late. A stall longer
        than one interval resets the schedule instead of trying to catch up in
        a burst.
        """
        now = self._now()
        if self._next is None:
            self._next = now + self.interval_s
            return 0.0
        wait = self._next - now
        if wait <= 0:
            self._next = now + self.interval_s
            return 0.0
        self._next += self.interval_s
        return wait

    def wait(self) -> float:
        delay = self.sleep_s()
        if delay > 0:
            time.sleep(delay)
        return delay


# ---------------------------------------------------------------------------
# The session — live, and never executed
# ---------------------------------------------------------------------------


@dataclass
class SessionStats:
    frames_sent: int = 0
    bytes_sent: int = 0
    records_received: int = 0
    events_injected: int = 0
    records_ignored: int = 0
    #: Records discarded because the PipeWire stream had no consumer yet, so
    #: injecting would have been a silent no-op for motion.
    records_dropped_no_consumer: int = 0
    #: Frames not transmitted because they were byte-identical to the last one
    #: sent and the keepalive was not yet due.
    frames_skipped: int = 0


class HostSession:
    """Connects to the iPad, streams frames and injects the input it sends back.

    **Never executed, and the one piece with nothing to check it against.**
    Each layer it calls is validated; their composition is not.

    Two gates the caller is responsible for, not this class:

    * **Sending bytes to the iPad needs the user's authorisation.** The
      2026-11-08 grant was for that session only.
    * **Creating a D-Bus session is user-visible** — a monitor appears and a
      screen-sharing indicator shows.

    ``display`` and ``source`` are injectable so the loop can be exercised with
    a fake socket and a solid-colour source, which is how its tests run.
    """

    def __init__(
        self,
        *,
        device_id: int | None = None,
        fps: int = TARGET_FPS,
        source: FrameSource | None = None,
        display: gnome.VirtualDisplaySession | None = None,
        inject: bool = True,
        skip_unchanged: bool = True,
        keepalive_interval_s: float = 1.0,
    ) -> None:
        #: None means "discover it from usbmuxd", which is what a host should
        #: do; an explicit id is only for tests and for forcing a device.
        self.device_id = device_id
        self.devices_seen: list[dict] = []
        self.fps = fps
        self.source = source
        self.display = display
        self.inject = inject
        #: Do not re-transmit a frame identical to the last one sent.
        self.skip_unchanged = skip_unchanged
        #: ...but never go longer than this without sending something, since
        #: the device's behaviour on a silent stream has never been observed.
        self.keepalive_interval_s = keepalive_interval_s
        self._last_sent: bytes | None = None
        self._last_send_at = 0.0
        self.stats = SessionStats()
        self.client_dimensions: tuple[int, int] | None = None
        self.diff_jpeg: bool = False
        self._socket = None
        self._demuxer = InboundDemuxer()

    # -- handshake --------------------------------------------------------

    def connect(self, socket_factory=None):
        """Open the usbmux socket and complete the decoded handshake.

        **This contacts the iPad.** Every step is the validated one from
        FED-START-E001, which succeeded against the real device first time; the
        only thing new here is that it is driven from this class.
        """
        if socket_factory is None:
            import socket as _socket  # noqa: PLC0415

            def socket_factory():
                sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
                sock.connect(usbmux.LINUX_USBMUXD_SOCKET)
                return sock

        self._socket = socket_factory()

        # Discover the device id rather than assume it. usbmuxd assigns a
        # fresh DeviceID on every attach, so a hard-coded one is right for a
        # single session and wrong for the next — met live on 2026-11-08 as a
        # BADDEV failure after a reconnect.
        if self.device_id is None:
            self._send(usbmux.build_list_devices())
            _, listing = usbmux.decode_message(self._recv_usbmux_message())
            devices = usbmux.parse_device_list(listing)
            self.device_id = usbmux.select_device(
                devices, product_id=usbmux.IPAD_PRODUCT_ID
            )
            self.devices_seen = devices
            # ListDevices is answered on its own connection; Connect needs a
            # fresh one, since a successful Connect turns the socket into the
            # device's byte stream.
            self._socket.close()
            self._socket = socket_factory()

        self._send(usbmux.build_connect(self.device_id))
        _, reply = usbmux.decode_message(self._recv_usbmux_message())
        if not usbmux.result_is_success(reply):
            name = usbmux.result_name(reply)
            hint = {
                "BADDEV": (
                    "usbmuxd does not know this device id. It is reassigned on "
                    "every attach, so this usually means the device detached "
                    "and came back."
                ),
                "CONNREFUSED": (
                    "nothing is listening on the application port — the "
                    "Splashtop app is not running or not in the foreground."
                ),
            }.get(name, "")
            raise HostError(
                f"usbmux Connect to device {self.device_id} failed: {name} "
                f"(Number={usbmux.parse_result(reply)}). {hint}"
            )

        # byte-order probe, then HELLO / READY / extra-data request
        probe, hello, ready, extra = startup.host_startup_sequence()
        self._send(probe)
        if not startup.probe_reply_accepted(self._recv_exactly(4)):
            raise HostError("the device rejected the byte-order probe")

        self._send(hello)
        self.client_dimensions = startup.parse_hello_ack(self._recv_exactly(16))

        self._send(ready)
        startup.parse_ready_ack(self._recv_exactly(16))

        self._send(extra)
        header = self._recv_exactly(4)
        body = self._recv_exactly(startup.extra_data_length(header))
        self.diff_jpeg = startup.diff_jpeg_enabled(body)
        if self.diff_jpeg:
            raise HostError(
                "the device enabled diff_jpeg, which this host cannot produce: "
                "the differential path is gated but was never observed, so "
                "nothing is known about what it transmits. Refusing to guess."
            )
        return self.client_dimensions

    # -- the loop ---------------------------------------------------------

    def run(self, *, frames: int | None = None, on_record=None) -> SessionStats:
        """Stream frames and apply inbound input until ``frames`` are sent.

        ``frames=None`` runs until the socket closes or the caller interrupts.
        Inbound records are drained each iteration rather than on a thread: the
        observed rate is modest (1,449 records in 45 seconds) and one loop is
        far easier to reason about than two.
        """
        if self._socket is None:
            raise HostError("not connected; call connect() first")
        if self.source is None:
            raise HostError("no frame source")

        pacer = Pacer(self.fps)
        sent = 0
        while frames is None or sent < frames:
            payload = self.source.next_payload()

            if self._should_send(payload):
                record = stream.encode_image_record(payload)
                self._send(record)
                self._last_sent = payload
                self._last_send_at = time.monotonic()
                self.stats.frames_sent += 1
                self.stats.bytes_sent += len(record)
            else:
                self.stats.frames_skipped += 1
            sent += 1

            self._drain_inbound(on_record)
            pacer.wait()
        return self.stats

    def _should_send(self, payload: bytes) -> bool:
        """Whether this frame is worth putting on the wire.

        **Why this exists.** Measured 2026-11-08: a frame is ~372 KB and the
        encode costs 4.9 ms against a 33 ms budget, so the host is nowhere near
        CPU-bound — it is bound by ~11 MB/s of USB for frames that are usually
        identical. A static desktop sent 999 byte-identical copies of one
        frame in a 38-second run.

        **The keepalive, and why transmission does not simply stop.** What the
        device does when a stream goes quiet has never been observed — the
        captured Windows session streamed continuously for its whole life, so
        there is no evidence either way about a timeout. Rather than guess,
        an unchanged frame is still re-sent, just at ``keepalive_interval_s``
        instead of every tick. At the default that is 1 fps instead of 30:
        roughly a 97% saving with no behaviour the device has not already
        seen.

        Identity is checked before equality because a repeated frame is
        normally the very same object — :class:`PipeWireFrameSource` returns
        its cached payload when nothing was damaged, and
        :class:`SolidColourSource` caches per colour — which makes the common
        case O(1) rather than a 372 KB comparison.
        """
        if not self.skip_unchanged or self._last_sent is None:
            return True
        unchanged = payload is self._last_sent or payload == self._last_sent
        if not unchanged:
            return True
        due = time.monotonic() - self._last_send_at >= self.keepalive_interval_s
        return due

    def _drain_inbound(self, on_record=None) -> None:
        """Read whatever input has arrived without blocking."""
        data = self._recv_available()
        if not data:
            return
        for record in self._demuxer.feed(data):
            self.stats.records_received += 1
            if on_record is not None:
                on_record(record)
            self._apply(record)

    def _apply(self, record: stream.TlvRecord) -> None:
        """Turn one record into pointer events, if it means anything.

        Only type 7 carries input — the only type ever observed inbound, and the
        only one the decode byte-swaps. Anything else is counted and dropped
        rather than interpreted, because nothing establishes what it means.
        """
        if record.tlv_type != stream.TLV_TYPE_7:
            self.stats.records_ignored += 1
            return
        if not self.inject or self.display is None:
            self.stats.records_ignored += 1
            return

        # Absolute motion is dropped until the PipeWire stream has a consumer,
        # and Mutter reports success anyway, so this cannot be detected from
        # the D-Bus reply. Capturing a frame proves a consumer exists.
        if not getattr(self.display, "stream_consumed", False):
            if (
                isinstance(self.source, PipeWireFrameSource)
                and self.source.frames_captured > 0
            ):
                self.display.stream_consumed = True
            else:
                self.stats.records_dropped_no_consumer += 1
                return

        calls = self.display.inject(record.field0, record.field1, record.field2)
        if calls:
            self.stats.events_injected += 1
        else:
            self.stats.records_ignored += 1

    # -- socket helpers ---------------------------------------------------

    def _send(self, data: bytes) -> None:
        """Send everything, checking the length.

        FED-STREAM-E001 noted that the agent checks its sends only against
        ``SOCKET_ERROR`` and never against the length, so a short send would
        silently corrupt the stream. ``sendall`` is the right answer, and this
        is one of the few places a host should deliberately not copy the agent.
        """
        self._socket.sendall(data)

    def _recv_exactly(self, count: int) -> bytes:
        chunks = []
        remaining = count
        while remaining > 0:
            chunk = self._socket.recv(remaining)
            if not chunk:
                raise HostError(
                    f"connection closed after {count - remaining} of {count} bytes"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_usbmux_message(self) -> bytes:
        header = self._recv_exactly(16)
        length, _, _, _ = usbmux.decode_header(header)
        return header + self._recv_exactly(length - 16)

    def _recv_available(self) -> bytes:
        """Read whatever input is already buffered, without blocking.

        Uses a zero timeout rather than ``select`` so that any socket-like
        object works, which is what lets the loop be tested without a real
        connection. An object with no ``settimeout`` cannot block by
        construction, so it is read directly.

        **A limitation worth naming:** a closed connection also yields no
        bytes, so this cannot by itself tell "no input yet" from "the device
        hung up". The outbound ``sendall`` is what surfaces a dead socket, on
        the next frame.
        """
        sock = self._socket
        settimeout = getattr(sock, "settimeout", None)
        if settimeout is None:
            return sock.recv(65536)
        previous = sock.gettimeout()
        settimeout(0)
        try:
            return sock.recv(65536)
        except (BlockingIOError, TimeoutError):
            return b""
        finally:
            settimeout(previous)

    def close(self) -> None:
        if self.source is not None:
            self.source.close()
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def __enter__(self) -> HostSession:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
