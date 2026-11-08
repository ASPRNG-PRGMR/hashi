"""usbmux client protocol for reaching the iPad's application port (FED-USBMUX-E001).

The Windows capture contains the complete usbmux control exchange that precedes
the application handshake, so this layer is derived from observed bytes rather
than from documentation guesswork.

**Fact, from the captured generation-3 exchange.** Each message is a 16-byte
little-endian header followed by an XML property list:

===========  ======  ==================================================
Field        Bytes   Observed value
===========  ======  ==================================================
length       0..4    total message length **including** the header
version      4..8    1
message      8..12   8  (plist protocol)
tag          12..16  caller-chosen; the reply echoes it (14 was observed)
===========  ======  ==================================================

The outgoing message was a 592-byte ``MessageType = Connect`` carrying
``DeviceID``, ``PortNumber``, ``BundleID``, ``ClientVersionString``
(``usbmuxd built for freedom``), ``ProgName`` (``libusbmuxd``) and
``kLibUSBMuxVersion = 3``. The reply was a 294-byte
``MessageType = Result`` with ``Number = 0``, tag echoed.

**Fact — the byte-swapped port, which is easy to get wrong.** The application
port is 6789 (``0x1a85``), but the plist carried ``PortNumber = 34074``
(``0x851a``). That is ``htons`` applied to the port and then stored as an
integer, which is what libusbmuxd does. WIN-START-E005 saw the same swap at the
``htons`` call site. A client must reproduce it.

**Scope and safety.** This module builds and parses byte strings. It performs no
I/O, opens no socket and connects to nothing. Opening a connection to the iPad's
application port is the Fedora-side replay the user declined; that step is not
taken here and needs explicit confirmation.
"""

import plistlib
import socket
import struct

#: Header field values observed throughout the capture.
USBMUX_VERSION_PLIST = 1
USBMUX_MESSAGE_PLIST = 8
USBMUX_HEADER_LEN = 16

#: The application port the agent connected to, in host byte order.
APPLICATION_PORT = 6789

#: Values the observed client identified itself with.
OBSERVED_CLIENT_VERSION_STRING = "usbmuxd built for freedom"
OBSERVED_PROG_NAME = "libusbmuxd"
OBSERVED_LIBUSBMUX_VERSION = 3

#: Where usbmuxd listens on Linux. Recorded for a caller to use; this module
#: never opens it.
LINUX_USBMUXD_SOCKET = "/var/run/usbmuxd"


class UsbmuxError(ValueError):
    pass


def htons_port(port: int) -> int:
    """Return the ``PortNumber`` value a Connect plist must carry.

    **Fact:** the capture shows port 6789 sent as 34074, i.e. ``htons``. On a
    little-endian host that is a 16-bit byte swap; :func:`socket.htons` is used
    so the result is correct on a big-endian host too, where it is a no-op.
    """
    if not 0 < port <= 0xFFFF:
        raise UsbmuxError(f"port must be 1..65535, got {port}")
    return socket.htons(port)


def encode_message(payload: dict, tag: int) -> bytes:
    """Frame one plist message exactly as observed.

    **Fact:** ``length`` counts the header, ``version`` is 1 and ``message`` is 8.
    """
    if not 0 <= tag <= 0xFFFFFFFF:
        raise UsbmuxError(f"tag must fit in 32 bits, got {tag}")
    body = plistlib.dumps(payload, fmt=plistlib.FMT_XML)
    header = struct.pack(
        "<IIII",
        USBMUX_HEADER_LEN + len(body),
        USBMUX_VERSION_PLIST,
        USBMUX_MESSAGE_PLIST,
        tag,
    )
    return header + body


def decode_header(header: bytes) -> tuple[int, int, int, int]:
    """Return ``(length, version, message, tag)`` from a 16-byte header."""
    if len(header) != USBMUX_HEADER_LEN:
        raise UsbmuxError(
            f"header must be exactly {USBMUX_HEADER_LEN} bytes, got {len(header)}"
        )
    length, version, message, tag = struct.unpack("<IIII", header)
    if length < USBMUX_HEADER_LEN:
        raise UsbmuxError(f"length {length} is shorter than the header")
    return length, version, message, tag


def decode_message(data: bytes) -> tuple[int, dict]:
    """Return ``(tag, plist)`` for one complete message.

    Rejects a version or message type other than the observed 1 and 8, since
    anything else is the binary protocol this module does not speak.
    """
    length, version, message, tag = decode_header(data[:USBMUX_HEADER_LEN])
    if version != USBMUX_VERSION_PLIST:
        raise UsbmuxError(f"unsupported usbmux version {version}")
    if message != USBMUX_MESSAGE_PLIST:
        raise UsbmuxError(f"unsupported usbmux message type {message}")
    if len(data) < length:
        raise UsbmuxError(f"truncated message: need {length} bytes, got {len(data)}")
    payload = plistlib.loads(data[USBMUX_HEADER_LEN:length])
    if not isinstance(payload, dict):
        raise UsbmuxError("usbmux payload is not a dictionary")
    return tag, payload


def _client_identity() -> dict:
    return {
        "ClientVersionString": OBSERVED_CLIENT_VERSION_STRING,
        "ProgName": OBSERVED_PROG_NAME,
        "kLibUSBMuxVersion": OBSERVED_LIBUSBMUX_VERSION,
    }


def build_list_devices(tag: int = 1) -> bytes:
    """A ``ListDevices`` request.

    **Observed** in the generation-1 and generation-2 exchanges. This asks the
    local daemon, not the device, so it does not touch the iPad's application
    port.
    """
    return encode_message({"MessageType": "ListDevices", **_client_identity()}, tag)


def build_connect(device_id: int, port: int = APPLICATION_PORT,
                  bundle_id: str | None = None, tag: int = 14) -> bytes:
    """A ``Connect`` request for ``port`` on ``device_id``.

    **Fact:** ``PortNumber`` carries the byte-swapped port — see
    :func:`htons_port`. The observed request also included a ``BundleID``;
    it is optional here because the capture does not establish that usbmuxd
    requires it.
    """
    if device_id < 0:
        raise UsbmuxError(f"device_id must be non-negative, got {device_id}")
    payload = {
        "MessageType": "Connect",
        "DeviceID": device_id,
        "PortNumber": htons_port(port),
        **_client_identity(),
    }
    if bundle_id is not None:
        payload["BundleID"] = bundle_id
    return encode_message(payload, tag)


def parse_result(payload: dict) -> int:
    """Return the ``Number`` of a ``Result`` reply.

    **Fact:** the observed successful reply was ``MessageType = Result`` with
    ``Number = 0``.
    """
    if payload.get("MessageType") != "Result":
        raise UsbmuxError(f"expected a Result, got {payload.get('MessageType')!r}")
    number = payload.get("Number")
    if not isinstance(number, int):
        raise UsbmuxError(f"Result has no integer Number: {number!r}")
    return number


def result_is_success(payload: dict) -> bool:
    """Whether a ``Result`` reply reports success, i.e. ``Number == 0``."""
    return parse_result(payload) == 0


#: usbmuxd's own ``Number`` codes, so a failure can be reported as something
#: better than an integer. Only 0 was ever observed in the captures; the rest
#: are usbmuxd's published result enum, and 2 was met live on 2026-11-08 when
#: the daemon had dropped the device.
#: The iPad's USB product id, ``05ac:12ab`` (FED-LIVE-E001, and unchanged on
#: 2026-11-08). Used only to prefer the right device when several are attached.
IPAD_PRODUCT_ID = 0x12AB

RESULT_NAMES = {
    0: "OK",
    1: "BADCOMMAND",
    2: "BADDEV",
    3: "CONNREFUSED",
    6: "BADVERSION",
}


def result_name(payload: dict) -> str:
    """A readable name for a ``Result`` reply's ``Number``."""
    number = parse_result(payload)
    return RESULT_NAMES.get(number, f"UNKNOWN({number})")


def parse_device_list(payload: dict) -> list[dict]:
    """Return the ``DeviceList`` of a ``ListDevices`` reply.

    Each entry is flattened to ``{"device_id", "serial", "product_id",
    "connection_type"}``. An empty list means usbmuxd currently knows of no
    device — which is **not** the same as no device being plugged in: on
    2026-11-08 the iPad was enumerated on USB (``05ac:12ab``) while usbmuxd
    reported an empty list, after an earlier session had used it successfully.
    """
    devices = payload.get("DeviceList", [])
    if not isinstance(devices, list):
        raise UsbmuxError(f"DeviceList is not a list: {devices!r}")
    out = []
    for entry in devices:
        properties = entry.get("Properties", {}) if isinstance(entry, dict) else {}
        out.append(
            {
                "device_id": entry.get("DeviceID"),
                "serial": properties.get("SerialNumber"),
                "product_id": properties.get("ProductID"),
                "connection_type": properties.get("ConnectionType"),
            }
        )
    return out


def select_device(devices: list[dict], *, product_id: int | None = None) -> int:
    """Pick the device id to connect to.

    **Why this exists.** The 2026-11-08 run hard-coded ``DeviceID = 1``, which
    was right for one session and wrong for the next: usbmuxd assigns a fresh
    id every time a device attaches, so a reconnect gets a different one and
    ``Connect`` fails with ``BADDEV``. A host must discover the id, never
    assume it.

    Prefers USB over network attachments, since HASHI is a wired display.
    """
    if not devices:
        raise UsbmuxError(
            "usbmuxd reports no devices. The iPad can be enumerated on USB and "
            "still be absent here — unlock it, make sure it trusts this host, "
            "and reopen the app; replugging the cable re-attaches it."
        )
    candidates = devices
    if product_id is not None:
        matching = [d for d in candidates if d.get("product_id") == product_id]
        if matching:
            candidates = matching
    usb = [d for d in candidates if d.get("connection_type") == "USB"]
    if usb:
        candidates = usb
    device_id = candidates[0].get("device_id")
    if not isinstance(device_id, int):
        raise UsbmuxError(f"device has no integer DeviceID: {candidates[0]!r}")
    return device_id
