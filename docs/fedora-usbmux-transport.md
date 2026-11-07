# usbmux transport — FED-USBMUX-E001

Offline work on Fedora, 2026-11-08, derived from the captured WIN-START-E002
usbmux control exchange. Nothing was sent to the iPad.

## Why this is observed rather than guessed

The capture retained the usbmux control bytes that precede the application
handshake: 592 outgoing and 294 incoming in the generation-3 streams, with
`ListDevices` exchanges in generations 1 and 2. So the transport layer is derived
from real bytes, and a Linux client can be validated against them offline — the
same discipline already applied to the handshake and the image stream.

## Message format

**Fact:** every message is a 16-byte **little-endian** header followed by an XML
property list.

| Field | Bytes | Observed |
| --- | --- | --- |
| length | 0..4 | total length **including** the 16-byte header |
| version | 4..8 | 1 |
| message | 8..12 | 8 (plist protocol) |
| tag | 12..16 | caller-chosen; the reply echoes it (14 observed) |

**Fact:** the outgoing message was `MessageType = Connect` carrying `DeviceID`,
`PortNumber`, `BundleID`, `ClientVersionString`
(`usbmuxd built for freedom`), `ProgName` (`libusbmuxd`) and
`kLibUSBMuxVersion = 3`. The reply was `MessageType = Result`, `Number = 0`,
with the tag echoed.

## The byte-swapped port

**Fact:** the application port is **6789** (`0x1a85`), but the plist carried
`PortNumber = 34074` (`0x851a`). That is `htons` applied to the port and stored
as an integer, which is what libusbmuxd does, and it matches the `htons` call
site WIN-START-E005 found statically. A client must reproduce the swap or the
connection targets the wrong port.

`hashi_usbmux.htons_port` uses `socket.htons` rather than an open-coded swap, so
it stays correct on a big-endian host where the operation is a no-op.

## Validation

Against the captured bytes, offline:

- the captured `Connect` and `Result` both parse;
- the reply's tag echoes the request's;
- the captured `PortNumber` equals `htons_port(6789)` exactly;
- `ClientVersionString`, `ProgName` and `kLibUSBMuxVersion` equal the module's
  constants;
- a `Connect` rebuilt from the captured field values is **semantically equal on
  every key**, and its header's version, message and tag fields are
  **byte-identical**.

**Why not byte-exact on the whole message:** usbmuxd parses property lists, so
key order and whitespace carry no meaning. Demanding byte equality of generated
XML would assert something the protocol does not require. The header, which *is*
positional, is checked byte-for-byte.

## Environment note

**Fact:** on this machine the usbmuxd **daemon** is active and the iPad is
enumerated on USB as `05ac:12ab`, but the libimobiledevice **command-line
tools** are absent. This corrects an earlier session's note. It is not a blocker:
the protocol above is simple enough to speak directly over
`/var/run/usbmuxd`, and doing so avoids a dependency whose absence would
otherwise have to be fixed first.

## What is deliberately not done

`hashi_usbmux` builds and parses byte strings. It performs **no I/O**, opens no
socket and connects to nothing — a test asserts the module's source contains no
`.connect(` or socket construction at all.

Two separate steps remain, and they are not equivalent:

1. **Querying the local daemon** (`ListDevices`) does not touch the iPad's
   application port. It is benign, and was not done here only because nothing
   needed it yet.
2. **Connecting to the iPad's port 6789** and sending the handshake *is* the
   Fedora-side replay the user declined earlier. That needs explicit
   confirmation and has not been taken.
