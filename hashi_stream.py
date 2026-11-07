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
