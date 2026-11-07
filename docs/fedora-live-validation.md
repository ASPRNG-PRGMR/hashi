# Live validation from Fedora — FED-LIVE-E001

2026-11-08. **The unmodified Splashtop iPad app displayed frames sent from
Fedora, and sent input back.** This is the first time HASHI has talked to the
device.

**Authorization:** the user granted explicit full authority to send bytes to the
iPad, superseding their earlier decline of a Fedora-side replay. Everything
before this point in the repository was built without any device contact.

Private evidence: run `fedora-live-20261107T200532Z`, index SHA-256
`392effd5dc0e7ae12e7ecfec6cb4bfd3d0915cea747f9eb12930bfcd7969e3ad`.

## Environment

| Item | Value |
| --- | --- |
| Host | Fedora 45, GNOME Shell 51.1, Wayland |
| iPad | USB `05ac:12ab`, usbmux `DeviceID = 1`, USB 480 Mbps |
| Application port | 6789 (`PortNumber = 34074`) |
| iPad app | Splashtop client, running and waiting |

## Stage 1 — handshake

**Fact:** the full decoded startup exchange succeeded on the first attempt.
576 bytes out, 346 in, clean close, no errors.

| Step | Result |
| --- | --- |
| usbmux `Connect` | `Result`, `Number = 0`, tag echoed |
| Byte-order probe | accepted — network byte order |
| HELLO → HELLO ACK | client dimensions **2048 × 1536** |
| READY → READY ACK | field 0 = `0xff` as required |
| `0xfc` → extra data | type 5, length 12, body `00 00 00 fd` + zeros |

**Fact — two independent confirmations of earlier static work.** The client
dimensions and the 12-byte extra-data block are **byte-identical to the Windows
capture**. So the `diff_jpeg` finding is confirmed as the device's real
behaviour rather than a one-off: the block is not valid JSON, the gate cannot
pass, and ordinary JPEG is genuinely the operative path.

## Stage 2 — outbound frames

**Fact:** 362 tag-6 records, 9,599,864 bytes, streamed at 30 fps as a
white → black → white pattern of 4 seconds each, using the user's own previously
captured 1280×960 frames. Every byte was accepted; the socket closed cleanly.

**Fact:** the user confirmed the pattern was visible on the iPad screen, and
further confirmed that what they saw was recognisably the **Windows desktop UI**
from the original capture.

That second detail is stronger evidence than "an image appeared". The replayed
frames are JPEGs of a Windows extended display, so recognising the Windows UI
means the frames decoded faithfully and the pixel content arrived intact — not
merely that the device accepted the bytes. It also makes the replay unmistakable
as a replay, which is exactly why it cannot stand in for frame generation.

So the whole outbound stack works end to end from Linux — usbmux transport,
startup handshake, record framing and JPEG frame format — all of it derived from
static reverse engineering and validated offline before any device contact.

**Limitation that matters:** the frames were *replayed*, not generated. This
validates transport, handshake, framing and the frame format. It does **not**
validate frame generation, which still needs the entropy coder.

## Stage 3 — inbound input

**Fact:** a 45-second window with 1,345 frames outbound captured **1,449 inbound
records, 23,184 bytes**, while the user tapped and swiped the screen. This closes
the "zero wire observations" limitation that governed FED-STREAM-E001's inbound
half.

Everything the static decode predicted held:

- **every** record was TLV **type 7** with a 12-byte big-endian payload and a
  `07 00 00 0c` header — the framing rule and the type-7 `ntohl` asymmetry both
  confirmed inbound;
- all 1,449 records were exactly 16 bytes, with **zero** truncation;
- coordinates spanned x 3..1236 and y 2..951, every value inside the 1280×960
  display's own pixel space — confirming the decoded input domain is display
  pixels.

**Fact — the field0 values observed:**

| `field0` | Count | Meaning |
| --- | --- | --- |
| 5 | 41 | pointer/touch **down** |
| 6 | 40 | pointer/touch **up** |
| 10 | 1,368 | pointer **motion** |

Downs and ups strictly alternate. A tap is `5 → 6` (seen 10 times); a drag is
`5 → 10 … → 6`, with 1,336 consecutive motion records across the window.

**This both confirms and extends the static analysis.** Static decoding had
already predicted 5 and 6 as `MOUSEEVENTF_LEFTDOWN` and `LEFTUP` purely from the
constants written into `mi.dwFlags`, and the live behaviour matches. `field0 = 10`
was the one value static analysis left unclassified — a separate dispatch path at
RVA `0x401c0` with no decoded purpose — and it is now established as motion.

## What remains unexercised

- **Only single-finger input.** No multi-touch, so the
  `InitializeTouchInjection`/`InjectTouchInput` `ContactID` path is still
  unobserved, as is the keyboard path (`field0` 1 and 2) and the `field0` 16/17
  `ProcControlMessage` path.
- `field0` values 3, 4, 7, 8, 9 and 11–17 were never seen.
- No reconfiguration, resize or rotation, so `SendReconfigVideo` and the TLV
  `0x70` subtype remain unexercised.
- `diff_jpeg` was not enabled by the device, so the differential path is still
  unexercised.
- One run, one device, one app version.

## Where this leaves the project

The protocol is no longer the risk. What remains is generation rather than
understanding:

1. the JPEG **entropy coder** — the only missing piece of outbound frames;
2. the Mutter **virtual monitor** and PipeWire capture, so frames come from a
   real extended display instead of a replay (see
   [Linux host architecture](linux-host-architecture.md));
3. **input injection** into the Linux session, mapping `field0` 5/6/10 onto
   `NotifyPointerButton` and `NotifyPointerMotionAbsolute` — now with observed
   event values to test against rather than inferred ones.
