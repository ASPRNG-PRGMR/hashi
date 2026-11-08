"""The startup handshake decoded from CProbeUsbmuxd::DoHandshake (RVA 0x303f0).

Evidence: FED-START-E001. Every rule here was read out of the instructions of the
unchanged agent
(SHA-256 cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c) and
then checked byte-for-byte against the captured WIN-START-E002 streams. Names
come from the vendor's own diagnostic format strings, not from guesswork:
``CProbeUsbmuxd::DoHandshake``, ``supported network byte order``,
``hello ack``, ``ready ack``, ``client resolution (%d, %d) -> (%d, %d)`` and
``recv extra data length failed``.

**Scope and safety.** This is a codec: it builds and parses byte strings. It
performs no I/O, opens no socket and talks to no device. Reproducing the
observed startup bytes offline is what it is for. Transmitting them to an iPad
is a separate decision the user has not taken, and nothing in this module does
it. The semantics of the ``0xfc`` field, of tag values beyond those observed, of
error paths and of every operating mode other than the one captured remain
unestablished; see docs/fedora-startup-handshake.md for the labelled limits.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Record types (the header's first byte)
# ---------------------------------------------------------------------------

#: Byte-order probe. Sent as a bare little-endian DWORD 4, not as a header.
TYPE_BYTE_ORDER_PROBE = 4
#: Fixed 12-byte control record used for the whole observed startup exchange.
TYPE_CONTROL = 5
#: Image record. Established as JPEG in WIN-START-E005; carried here as a
#: constant only, since this module does not encode images.
TYPE_IMAGE = 6
#: The type used by the fallback path when the byte-order probe fails.
TYPE_CONTROL_LEGACY = 1

# ---------------------------------------------------------------------------
# Control-record field 0 values, named from the agent's log strings
# ---------------------------------------------------------------------------

MSG_HELLO = 0x01         # host -> device
MSG_HELLO_ACK = 0x02     # device -> host; carries client width/height
MSG_READY = 0xFE         # host -> device
MSG_READY_ACK = 0xFF     # device -> host
MSG_EXTRA_REQUEST = 0xFC  # host -> host-visible request preceding "extra data"
MSG_EXTRA_ACK = 0xFD     # device -> host

#: Payload length of every control record in the observed exchange.
CONTROL_PAYLOAD_LEN = 12
#: Total wire size of a control record: 4-byte header + 12-byte payload.
CONTROL_RECORD_LEN = 16

# ---------------------------------------------------------------------------
# Timeouts the agent uses, in milliseconds (ECX into helper 0x4112d0)
# ---------------------------------------------------------------------------

TIMEOUT_CONTROL_MS = 5000   # 0x1388, the fixed 16-byte exchanges
TIMEOUT_EXTRA_HEADER_MS = 500  # 0x1f4, the final 4-byte header read
TIMEOUT_EXTRA_BODY_MS = 300    # 0x12c, each body chunk
#: The body loop gives up once its counter exceeds 10 (``cmp edx,0xa``).
EXTRA_BODY_MAX_ATTEMPTS = 11


class StartupError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Header codec
# ---------------------------------------------------------------------------

def encode_header(record_type: int, payload_len: int) -> bytes:
    """Return the 4-byte record header.

    **Fact.** The agent builds the header word as
    ``(htonl(len << 8) << 8) | type`` at RVA 0x3055f-0x30562 and stores it
    little-endian, which places the type in byte 0 and the length in bytes 1-3
    big-endian. Expressed directly, that is ``[type, len>>16, len>>8, len]``.
    """
    if not 0 <= record_type <= 0xFF:
        raise StartupError(f"record type {record_type} does not fit in a byte")
    if not 0 <= payload_len <= 0xFFFFFF:
        raise StartupError(f"payload length {payload_len} does not fit in 24 bits")
    return bytes([record_type]) + payload_len.to_bytes(3, "big")


def decode_header(header: bytes) -> tuple[int, int]:
    """Return ``(record_type, payload_len)`` from a 4-byte header.

    **Fact.** The agent reverses its own construction at RVA 0x3087b-0x3089e:
    it masks the type byte off, byte-swaps the remainder, shifts the type back
    in and takes the top 24 bits as the length.
    """
    if len(header) != 4:
        raise StartupError(f"header must be exactly 4 bytes, got {len(header)}")
    return header[0], int.from_bytes(header[1:4], "big")


# ---------------------------------------------------------------------------
# Control-record codec
# ---------------------------------------------------------------------------

def encode_control(
    field0: int,
    field1: int = 0,
    field2: int = 0,
    *,
    network_order: bool = True,
    raw_field1: bool = False,
) -> bytes:
    """Build one 16-byte control record.

    **Fact.** Each of the three payload fields is a 32-bit word passed through
    ``htonl`` when the byte-order probe succeeded, and stored natively
    otherwise (RVA 0x30570/0x3057e, 0x306be/0x306cf, 0x30806/0x30817).

    ``raw_field1`` reproduces a real inconsistency in the agent rather than a
    choice of ours: for the ``0xfc`` record, field 1 is written as a plain
    ``mov`` of the literal 5 at RVA 0x30829 with **no** ``htonl``, unlike every
    sibling field. The captured bytes confirm it: field 0 is big-endian ``0xfc``
    while field 1 is little-endian ``5``.
    """
    order = "big" if network_order else "little"
    f1_order = "little" if raw_field1 else order
    for name, value in (("field0", field0), ("field1", field1), ("field2", field2)):
        if not 0 <= value <= 0xFFFFFFFF:
            raise StartupError(f"{name} {value} does not fit in 32 bits")
    payload = (
        field0.to_bytes(4, order)
        + field1.to_bytes(4, f1_order)
        + field2.to_bytes(4, order)
    )
    record_type = TYPE_CONTROL if network_order else TYPE_CONTROL_LEGACY
    return encode_header(record_type, CONTROL_PAYLOAD_LEN) + payload


@dataclass(frozen=True)
class ControlRecord:
    record_type: int
    field0: int
    field1: int
    field2: int


def decode_control(record: bytes, *, network_order: bool = True) -> ControlRecord:
    """Parse one 16-byte control record.

    **Fact.** The agent requires each fixed read to return exactly 16 bytes
    (``cmp edi,0x10``; RVA 0x3059c, 0x305d4) and byte-swaps the fields with
    ``ntohl`` only in network-order mode.
    """
    if len(record) != CONTROL_RECORD_LEN:
        raise StartupError(
            f"control record must be exactly {CONTROL_RECORD_LEN} bytes, "
            f"got {len(record)}"
        )
    record_type, payload_len = decode_header(record[:4])
    if payload_len != CONTROL_PAYLOAD_LEN:
        raise StartupError(f"expected payload length 12, got {payload_len}")
    order = "big" if network_order else "little"
    f = [int.from_bytes(record[4 + 4 * i: 8 + 4 * i], order) for i in range(3)]
    return ControlRecord(record_type, f[0], f[1], f[2])


# ---------------------------------------------------------------------------
# Host-side sequence and validation
# ---------------------------------------------------------------------------

def encode_byte_order_probe() -> bytes:
    """Return the 4-byte byte-order probe.

    **Fact.** RVA 0x3046e stores the literal DWORD 4 into the send buffer and
    sends 4 bytes. It is an integer, not a header — the bytes coincide with a
    type-4 zero-length record, so the two readings are indistinguishable on the
    wire. The agent's own log for a successful reply is
    ``supported network byte order``.
    """
    return (4).to_bytes(4, "little")


def host_startup_sequence(*, network_order: bool = True) -> list[bytes]:
    """Return the four host->device messages, in order, exactly as observed.

    **Fact**, validated byte-for-byte against the captured outgoing stream.
    """
    return [
        encode_byte_order_probe(),
        encode_control(MSG_HELLO, network_order=network_order),
        encode_control(MSG_READY, network_order=network_order),
        encode_control(
            MSG_EXTRA_REQUEST, 5, network_order=network_order, raw_field1=True
        ),
    ]


def probe_reply_accepted(reply: bytes) -> bool:
    """Whether the agent would accept the byte-order probe reply.

    **Fact.** RVA 0x3046e-0x30485 requires the send to return exactly 4, and
    RVA 0x304d2 compares only **byte 0** of the reply against 4. The remaining
    three bytes are not examined.
    """
    if len(reply) < 1:
        return False
    return reply[0] == TYPE_BYTE_ORDER_PROBE


def align_client_dimension(value: int) -> int:
    """Round a client dimension the way the agent does before storing it.

    **Fact.** RVA 0x30783-0x3078c computes ``((value - 1) & ~3) + 4`` for the
    width and the same for the height at 0x30792-0x3079b, storing them to shared
    state ``+0x14`` and ``+0x18``. The agent logs the pair as
    ``client resolution (%d, %d) -> (%d, %d)``. Note this is not a plain
    round-up: a value already a multiple of 4 is returned unchanged, and the
    expression is only meaningful for positive values.
    """
    if value <= 0:
        raise StartupError(f"client dimension must be positive, got {value}")
    return ((value - 1) & ~3) + 4


def parse_hello_ack(record: bytes, *, network_order: bool = True) -> tuple[int, int]:
    """Validate a HELLO ACK and return the aligned ``(width, height)``.

    **Fact.** RVA 0x305f6 requires field 0 to equal 2 — the agent logs
    ``hello ack unknown type`` otherwise — and RVA 0x30659-0x3067c reads the
    client width from field 1 and the height from field 2.
    """
    control = decode_control(record, network_order=network_order)
    if control.field0 != MSG_HELLO_ACK:
        raise StartupError(
            f"hello ack unknown type: expected {MSG_HELLO_ACK}, got {control.field0}"
        )
    return (
        align_client_dimension(control.field1),
        align_client_dimension(control.field2),
    )


def parse_ready_ack(record: bytes, *, network_order: bool = True) -> None:
    """Validate a READY ACK.

    **Fact.** RVA 0x30748 requires field 0 to equal 0xff; the agent logs
    ``ready ack unknown type`` otherwise.
    """
    control = decode_control(record, network_order=network_order)
    if control.field0 != MSG_READY_ACK:
        raise StartupError(
            f"ready ack unknown type: expected {MSG_READY_ACK}, got {control.field0}"
        )


def extra_data_length(header: bytes) -> int:
    """Return the announced length of the trailing "extra data" block.

    **Fact.** The final exchange is not a fixed 16-byte read. RVA 0x3084e reads
    exactly 4 header bytes, 0x3089e takes the 24-bit length, 0x308a1 rejects a
    zero length (logging ``recv extra data length failed``), 0x308ca allocates
    ``length + 1`` bytes, and 0x308ea loops receiving until the full length
    arrives. This is why the captured 16-byte reply appeared as a 4-byte read
    followed by a 12-byte read: the split is by design, not a network artifact.
    """
    _, length = decode_header(header)
    if length == 0:
        raise StartupError("recv extra data length failed: announced length is zero")
    return length


# ---------------------------------------------------------------------------
# The trailing "extra data" block is a JSON capability document
# ---------------------------------------------------------------------------

#: The only capability key the agent inspects (string at VA 0x5ab0b4).
CAPABILITY_DIFF_JPEG = "diff_jpeg"

#: Shared-state offset the result is written to. Per the established field
#: table, +0x68 chooses differential JPEG when +0x64 is zero.
SHARED_OFFSET_DIFF_JPEG = 0x68


def parse_capability_document(body: bytes) -> dict:
    """Parse the trailing "extra data" block as the agent does.

    **Fact.** RVA 0x309a0-0x30ac5, inside ``CProbeUsbmuxd::DoHandshake``, feeds
    the received block to a JSON parser and logs
    ``parse extra data failed, %s`` on failure. The parser is JsonCpp or a close
    relative — its error strings are present verbatim in ``.rdata``, including
    "A valid JSON document must be either an array or an object value." and
    "Syntax error: value, object or array expected."

    Returns the decoded object on success. Raises :class:`StartupError` when the
    block is not a valid JSON document, which is what the agent treats as
    failure.
    """
    import json

    if not body:
        raise StartupError("parse extra data failed: empty block")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise StartupError(f"parse extra data failed, {exc}") from exc
    if not isinstance(value, (dict, list)):
        raise StartupError(
            "parse extra data failed, A valid JSON document must be either "
            "an array or an object value."
        )
    return value


def diff_jpeg_enabled(body: bytes) -> bool:
    """Whether the agent would set shared ``+0x68`` from this extra-data block.

    **Fact.** The gate is a three-step chain at RVA 0x30a31-0x30a75, each step
    falling through to ``+0x68 = 0`` on failure:

    1. the document contains the key ``diff_jpeg`` (RVA 0x30a40);
    2. that member is a boolean (RVA 0x30a57);
    3. its value is true (RVA 0x30a6e).

    Only then does RVA 0x30a83 store 1 to ``+0x68`` and log
    ``enable jpeg diff stream``. A malformed document, a missing key, a
    non-boolean value or ``false`` all leave differential JPEG off.

    This function returns False for every failure mode rather than raising,
    matching the agent's behaviour of treating them all as "not enabled".
    """
    try:
        document = parse_capability_document(body)
    except StartupError:
        return False
    if not isinstance(document, dict):
        return False
    value = document.get(CAPABILITY_DIFF_JPEG)
    # Step 2 is an explicit is-boolean test, so 1 / "true" / non-bool truthy
    # values do not qualify.
    if not isinstance(value, bool):
        return False
    return value
