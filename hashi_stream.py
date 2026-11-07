"""The steady-state loop decoded from CConnectBase (FED-STREAM-E001).

Two threads in the agent, named by its own diagnostic strings:

* ``CConnectBase::Run`` (RVA 0x2f580) — the outbound frame loop. Builds a
  4-byte header, sends it, sends the payload, logs ``Bytes Sent``, then paces
  itself to the configured frame rate.
* ``CConnectBase::ReceiveThread`` (RVA ~0x2f8c0) — the inbound TLV loop. Reads a
  4-byte header, allocates and fills the payload, then dispatches on the type.

**Confidence is not uniform here, and the split matters.**

The outbound side is **Fact** corroborated on the wire: WIN-START-E005 captured
1,903 outbound image records, and ``hashi_framing``/``hashi_startup`` already
reproduce every one of their headers byte-for-byte.

The inbound TLV side is **static-only**. The captured session contains exactly
**zero** steady-state incoming bytes — the generation-3 incoming stream is 346
bytes, all of it the usbmux control exchange plus the 52-byte startup, with
nothing after. So TLV types 3 and 7 and the subtypes 0x70/0x71 are read out of
instructions and have **never been seen on the wire**. Do not treat the inbound
parser as validated, and do not infer what the fields mean.

This module performs no I/O. It opens no socket and talks to no device.
See docs/fedora-steady-state.md for the labelled evidence and limits.
"""

from dataclasses import dataclass

from hashi_startup import StartupError, decode_header, encode_header

# ---------------------------------------------------------------------------
# Outbound frame loop — CConnectBase::Run
# ---------------------------------------------------------------------------

#: Image record type, as observed for all 1,903 captured frames.
TYPE_IMAGE = 6

#: ``GetSystemTime`` is sampled once per iteration and only its
#: ``wMilliseconds`` field is used, so the agent's own elapsed measurement wraps
#: every 1000 ms (RVA 0x2f74a-0x2f753).
PACING_WRAP_MS = 1000


class StreamError(ValueError):
    pass


def encode_image_record(payload: bytes) -> bytes:
    """Return the on-wire bytes of one outbound image record.

    **Fact.** ``CConnectBase::Run`` builds the header with exactly the same rule
    as the handshake — ``(htonl(len << 8) << 8) | type`` in network-order mode
    and ``(len << 8) | type`` natively, gated on the same shared ``+0x40`` flag
    (RVA 0x2f6c5-0x2f6ee) — then issues **two** sends: 4 header bytes at RVA
    0x2f702 and the payload at RVA 0x2f718. Over a byte stream those two sends
    are indistinguishable from the single buffer this function returns, which is
    why the captured stream parses as contiguous records.

    **Fact / limitation worth knowing:** both sends are checked only against
    ``SOCKET_ERROR`` (``cmp eax,0xffffffff``), *not* against the requested
    length, unlike the handshake which requires exact counts. A partial send
    would therefore go unnoticed by the agent. In the captured session every
    accepted length equalled the requested one, so this never manifested.
    """
    if not payload:
        raise StreamError("refusing to encode an empty image record")
    return encode_header(TYPE_IMAGE, len(payload)) + payload


def frame_interval_ms(fps: int) -> int:
    """Target milliseconds per frame.

    **Fact.** RVA 0x2f759-0x2f75f computes ``1000 / fps`` with a signed integer
    division, so the interval truncates.
    """
    if fps <= 0:
        raise StreamError(f"fps must be positive, got {fps}")
    return PACING_WRAP_MS // fps


def pacing_sleep_ms(previous_ms: int, current_ms: int, fps: int) -> int:
    """Milliseconds the agent would sleep before producing the next frame.

    **Fact.** RVA 0x2f74a-0x2f76a: take the elapsed time as
    ``current_ms - previous_ms``, add 1000 if that went negative, compare
    against ``1000 / fps`` and sleep the remainder only when the elapsed time
    is smaller. Both inputs are the ``wMilliseconds`` field of ``GetSystemTime``
    (UTC), so each is in 0..999 and the measurement cannot distinguish an
    interval longer than one second from a short one.
    """
    for name, value in (("previous_ms", previous_ms), ("current_ms", current_ms)):
        if not 0 <= value < PACING_WRAP_MS:
            raise StreamError(f"{name} must be a wMilliseconds value 0..999, got {value}")
    elapsed = current_ms - previous_ms
    if elapsed < 0:
        elapsed += PACING_WRAP_MS
    target = frame_interval_ms(fps)
    return target - elapsed if elapsed < target else 0


# ---------------------------------------------------------------------------
# Inbound TLV loop — CConnectBase::ReceiveThread  (STATIC ONLY, NEVER OBSERVED)
# ---------------------------------------------------------------------------

#: The only two TLV types the agent dispatches. Every other value reaches the
#: ``unknown type(%d), x/w(%d), y/h(%d)`` log and is otherwise ignored.
TLV_TYPE_3 = 3
TLV_TYPE_7 = 7
TLV_HANDLED_TYPES = (TLV_TYPE_3, TLV_TYPE_7)

#: Payload bytes retained per record. RVA 0x2fb45 clamps the announced length to
#: 12, so a longer record is truncated rather than rejected.
TLV_PAYLOAD_CLAMP = 12

#: Records land in a 64-slot ring of 12-byte entries, indexed modulo 64
#: (RVA 0x2fb1e-0x2fb2f).
TLV_RING_SLOTS = 64

#: Inner subtype values recognised from field 0 (RVA 0x2fb84-0x2fb90).
#: 0x71 is logged as ``video type(%d)``; 0x70 takes its own branch whose purpose
#: this slice does not establish. Anything else goes to handler 0x440110.
TLV_SUBTYPE_70 = 0x70
TLV_SUBTYPE_VIDEO = 0x71

#: Receive poll timeout, RVA 0x2f907 / 0x2fa4c (0xbb8).
TIMEOUT_RECV_MS = 3000


@dataclass(frozen=True)
class TlvRecord:
    tlv_type: int
    field0: int
    field1: int
    field2: int
    handled: bool
    truncated: bool


def tlv_payload_is_network_order(tlv_type: int) -> bool:
    """Whether the agent byte-swaps a TLV payload of this type.

    **Fact, and an asymmetry worth not smoothing over.** RVA 0x2fb5e-0x2fb7f
    applies ``ntohl`` to all three payload fields **only** when the type is 7,
    and does so *unconditionally* — it does not consult the negotiated
    ``+0x40`` byte-order flag the way the header decode at RVA 0x2f9d9 does.
    Type 3 payloads are left in native order.
    """
    return tlv_type == TLV_TYPE_7


def parse_tlv_record(header: bytes, payload: bytes) -> TlvRecord:
    """Parse one inbound TLV record.

    **Static only — never observed on the wire.** The header is the same
    type-byte + BE24-length form used everywhere else (RVA 0x2f9d9-0x2fa02).
    The payload is clamped to 12 bytes, copied into a ring slot, and its three
    32-bit fields are byte-swapped for type 7 and left native for type 3.

    Fields are deliberately named ``field0/1/2`` rather than given meanings. The
    agent logs them as ``type(%d), x/w(%d), y/h(%d)``, which shows one field is
    read as either an x coordinate or a width depending on context, but which
    type means which is **not** established and must not be guessed.
    """
    tlv_type, announced = decode_header(header)
    if announced == 0:
        raise StreamError("TLV record announces a zero-length payload")
    kept = min(announced, TLV_PAYLOAD_CLAMP)
    if len(payload) < kept:
        raise StreamError(
            f"TLV payload short: need {kept} bytes, got {len(payload)}"
        )
    body = payload[:kept].ljust(TLV_PAYLOAD_CLAMP, b"\x00")
    order = "big" if tlv_payload_is_network_order(tlv_type) else "little"
    fields = [int.from_bytes(body[4 * i: 4 * i + 4], order) for i in range(3)]
    return TlvRecord(
        tlv_type=tlv_type,
        field0=fields[0],
        field1=fields[1],
        field2=fields[2],
        handled=tlv_type in TLV_HANDLED_TYPES,
        truncated=announced > TLV_PAYLOAD_CLAMP,
    )


def tlv_ring_slot(sequence: int) -> int:
    """Ring slot a record with this sequence number would occupy.

    **Fact.** RVA 0x2fb1e-0x2fb29 masks with ``0x8000003f`` and applies a sign
    fixup, which is the compiler's signed ``% 64``. Python's ``%`` differs for
    negatives, so negatives are rejected here rather than silently remapped.
    """
    if sequence < 0:
        raise StreamError(f"sequence must be non-negative, got {sequence}")
    return sequence % TLV_RING_SLOTS


# ---------------------------------------------------------------------------
# Inbound input dispatch — handler 0x440110  (STATIC ONLY, NEVER OBSERVED)
# ---------------------------------------------------------------------------

#: Jump-table targets at VA 0x4404f8, read from the image as data (objdump
#: renders the table as instructions). Index is ``field0 - 1``, valid for
#: field0 in 1..17; anything above reaches the epilogue directly.
#: Mapped as {field0: target RVA}.
INPUT_DISPATCH_TABLE = {
    1: 0x40132, 2: 0x40132,
    3: 0x404ED,
    4: 0x4027C, 7: 0x4027C,
    5: 0x40254, 6: 0x4025B, 8: 0x40262, 9: 0x40269,
    10: 0x401C0,
    11: 0x404ED, 12: 0x404ED, 13: 0x404ED,
    14: 0x40270, 15: 0x40277,
    16: 0x40386, 17: 0x40386,
}

#: RVA of the shared epilogue. A field0 routed here is accepted and discarded.
INPUT_DISPATCH_EPILOGUE = 0x404ED

#: field0 values the table routes straight to the epilogue, i.e. recognised as
#: in range but not acted on.
INPUT_IGNORED = (3, 11, 12, 13)

#: Highest field0 the table covers (``cmp eax,0x10; ja`` at RVA 0x40122).
INPUT_DISPATCH_MAX = 17

#: Size of the structure the handler builds before calling SendInput
#: (``push 0x1c`` at RVA 0x40197). Matches Win32 INPUT on x86.
WIN32_INPUT_SIZE = 28


def input_dispatch_target(field0: int) -> int | None:
    """Jump-table target RVA for a TLV ``field0``, or None if out of range.

    **Fact.** Handler ``0x440110`` computes ``field0 - 1``, rejects anything
    above 0x10 (RVA 0x40122), and jumps through the table at VA 0x4404f8. It
    builds a 28-byte structure and calls **``SendInput``** (IAT 0x57b77c) at RVA
    0x401a8 and 0x40244, so this path injects input into the Windows session.

    **Static only — never observed on the wire.** No inbound record was captured.
    """
    if field0 < 1 or field0 > INPUT_DISPATCH_MAX:
        return None
    return INPUT_DISPATCH_TABLE[field0]


def input_is_acted_on(field0: int) -> bool:
    """Whether a ``field0`` reaches a real handler rather than the epilogue."""
    target = input_dispatch_target(field0)
    return target is not None and target != INPUT_DISPATCH_EPILOGUE


# ---------------------------------------------------------------------------
# Outbound video reconfiguration — CConnectBase::SendReconfigVideo
# ---------------------------------------------------------------------------

#: Control-record field 0 used to announce host video configuration. The startup
#: HELLO uses the same value with zero dimensions, and the device answers with
#: field 0 = 2 carrying its own, so 1 is "host side" and 2 is "client side".
MSG_VIDEO_CONFIG = 0x01


def encode_reconfig_video(
    output_width: int,
    output_height: int,
    *,
    transposed: bool = False,
    network_order: bool = True,
) -> bytes:
    """Build the record ``CConnectBase::SendReconfigVideo`` sends.

    **Fact, decoded from instructions at RVA 0x2f243-0x2f29a.** It is a 16-byte
    control record: the usual type-byte + BE24-length header, field 0 = 1, and
    fields 1 and 2 taken from shared state ``+0x1c``/``+0x20`` — the *output*
    dimensions established by FED-MODE-E001 as the selected monitor's
    ``rcMonitor`` extent. Each is passed through ``htonl``. Failure logs
    ``send video config failed: %d``.

    **Fact:** the order of the two dimensions is swapped when shared ``+0x24``
    is nonzero (RVA 0x2f257-0x2f286), which ``transposed`` models.

    **Inference:** ``+0x24`` being a transpose flag is consistent with a
    rotation or orientation state, but this slice does not establish what sets
    it.

    **Never observed on the wire.** No reconfiguration occurred during the
    captured session, so unlike the startup sequence this encoder has no
    byte-exact validation. It is decoded, not guessed — but it is also not
    confirmed. Nothing in this repository transmits it.
    """
    from hashi_startup import encode_control  # local import: codec reuse only

    for name, value in (("output_width", output_width), ("output_height", output_height)):
        if value <= 0:
            raise StreamError(f"{name} must be positive, got {value}")
    first, second = (
        (output_height, output_width) if transposed else (output_width, output_height)
    )
    return encode_control(
        MSG_VIDEO_CONFIG, first, second, network_order=network_order
    )


# ---------------------------------------------------------------------------
# Input event kinds — CInput, handler 0x440110  (STATIC ONLY, NEVER OBSERVED)
# ---------------------------------------------------------------------------

# Documented Win32 MOUSEEVENTF_* values, restated here so the mapping below can
# be checked against the constants the agent actually writes into mi.dwFlags.
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

#: Flags the agent writes for a positioned move: MOVE | VIRTUALDESK | ABSOLUTE
#: (``mov DWORD PTR [esp+0x38],0xc001`` at RVA 0x40313).
MOUSE_MOVE_FLAGS = MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_ABSOLUTE

#: Win32 requires ABSOLUTE coordinates normalised to 0..65535. The agent
#: multiplies by the double constant at VA 0x5ad930, which is exactly 65535.0
#: (RVA 0x4032f, 0x40355).
ABSOLUTE_COORD_MAX = 65535

#: ``field0`` -> the MOUSEEVENTF_* value written into ``mi.dwFlags``.
#: **Fact:** each of the six 7-byte stubs at RVA 0x40254-0x40277 sets exactly one
#: of these constants into EBP, which RVA 0x402bd stores to ``mi.dwFlags``. The
#: values match the documented Win32 button constants exactly, in down/up order.
MOUSE_BUTTON_FLAGS = {
    5: MOUSEEVENTF_LEFTDOWN,
    6: MOUSEEVENTF_LEFTUP,
    8: MOUSEEVENTF_RIGHTDOWN,
    9: MOUSEEVENTF_RIGHTUP,
    14: MOUSEEVENTF_MIDDLEDOWN,
    15: MOUSEEVENTF_MIDDLEUP,
}

#: ``field0`` values that enter the same mouse path without a button stub, so
#: EBP keeps the ``xor ebp,ebp`` zero from RVA 0x4011f.
#: **Inference:** movement-only events.
MOUSE_MOVE_ONLY = (4, 7)

#: ``field0`` values routed to the keyboard path at RVA 0x40132, which fills a
#: KEYBDINPUT ``wVk``/``wScan`` pair before SendInput.
KEYBOARD_FIELD0 = (1, 2)

#: ``field0`` values routed to the CInput::ProcControlMessage path at RVA
#: 0x40386, which reads ``field2`` as two packed 16-bit halves.
CONTROL_MESSAGE_FIELD0 = (16, 17)

#: Win32 touch-injection entry points the agent resolves by name. Touch is not
#: delivered through SendInput.
TOUCH_INJECTION_SYMBOLS = ("InitializeTouchInjection", "InjectTouchInput")


def mouse_flags_for(field0: int) -> int | None:
    """``mi.dwFlags`` the agent would use for a zero-coordinate event.

    **Fact** for the six button values, whose constants match Win32 exactly.
    Returns 0 for the movement-only values, whose stub-free path leaves EBP at
    zero, and None for a ``field0`` that is not on the mouse path at all.

    **Static only — never observed on the wire.**
    """
    if field0 in MOUSE_BUTTON_FLAGS:
        return MOUSE_BUTTON_FLAGS[field0]
    if field0 in MOUSE_MOVE_ONLY:
        return 0
    return None


def normalise_absolute(value: int, span: int) -> int:
    """Normalise a single coordinate to the Win32 absolute 0..65535 range.

    Convenience form of :func:`to_virtual_desktop_absolute` with no monitor
    offset, i.e. for a span that already starts at the desktop origin.
    """
    return to_virtual_desktop_absolute(value, 0, 0, span)


def to_virtual_desktop_absolute(
    value: int, monitor_origin: int, desktop_origin: int, desktop_span: int
) -> int:
    """Map one monitor-relative coordinate to a virtual-desktop absolute value.

    **Fact — the full arithmetic, now decoded.** The positioned path at RVA
    0x40310-0x40360 adds two per-axis doubles and multiplies by 65535.0:

    * the scale term (RVA 0x40760 for x, 0x407c0 for y) is
      ``value / monitorinfo[+0x1c]`` for x and ``/ monitorinfo[+0x20]`` for y;
    * the offset term (RVA 0x406e0 for x, 0x40720 for y) is
      ``(origin_getter() - monitorinfo[+0x0c]) / monitorinfo[+0x1c]`` for x, and
      the same with ``+0x10`` / ``+0x20`` for y;
    * the origin getters are RVA 0xcd00 returning the selected monitor record's
      ``+0x00`` (left) and RVA 0xcd70 returning its ``+0x04`` (top) — the same
      32-byte records FED-MODE-E001 established.

    Both terms share the denominator, so the whole transform is

    ``((value + monitor_origin - desktop_origin) / desktop_span) * 65535``

    truncated to an int, with ``mi.dwFlags`` set to
    ``MOVE | VIRTUALDESK | ABSOLUTE``.

    **Inference:** ``monitorinfo[+0x0c]/+0x10`` and ``+0x1c/+0x20`` are the
    virtual desktop's origin and extent. The `MOUSEEVENTF_VIRTUALDESK` flag
    requires normalisation across the whole desktop, and adding the selected
    monitor's origin only makes sense against a desktop-wide denominator, so
    this reading is strongly supported — but the fields were not independently
    confirmed to be desktop rather than monitor metrics.

    **Consequence:** incoming coordinates are **monitor-relative pixels**, not
    pre-normalised values. A host must know the monitor's placement inside the
    desktop to place them.
    """
    if desktop_span <= 0:
        raise StreamError(f"desktop_span must be positive, got {desktop_span}")
    offset = value + monitor_origin - desktop_origin
    if not 0 <= offset <= desktop_span:
        raise StreamError(
            f"coordinate {value} maps to {offset}, outside 0..{desktop_span}"
        )
    return int(offset / desktop_span * ABSOLUTE_COORD_MAX)


def input_kind(field0: int) -> str:
    """Coarse classification of a ``field0``, by which dispatch path it takes.

    **Fact** for the routing; the labels are the agent's own, from its symbol
    and log strings. ``"ignored"`` means in range but sent to the epilogue.

    **Static only — never observed on the wire.** Returns ``"out-of-range"``
    above 17, which includes the video subtypes 0x70 and 0x71 handled elsewhere.
    """
    if field0 in KEYBOARD_FIELD0:
        return "keyboard"
    if field0 in MOUSE_BUTTON_FLAGS:
        return "mouse-button"
    if field0 in MOUSE_MOVE_ONLY:
        return "mouse-move"
    if field0 in INPUT_IGNORED:
        return "ignored"
    if field0 in CONTROL_MESSAGE_FIELD0:
        return "control-message"
    if 1 <= field0 <= INPUT_DISPATCH_MAX:
        return "other"
    return "out-of-range"
