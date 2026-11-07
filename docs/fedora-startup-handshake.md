# Startup handshake decoded — FED-START-E001

Static continuation on Fedora, 2026-11-07. Target: the unchanged agent SHA-256
`cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`, `pei-i386`,
preferred base `0x400000`. All addresses are module-relative **RVAs**. Tool: GNU
objdump 2.47.20260726, static disassembly only — the target was never executed,
and nothing was transmitted to the iPad. Private evidence: analysis run index
SHA-256 `73634a08d0e9b7b7823716de8bd8f79acf7aca0970553ffd0bf889aadf0215cd`.

## What this establishes

**Fact:** The entire observed startup exchange lives in **one** function at RVA
`0x303f0`, 0x792 bytes and 563 instructions, which the agent's own diagnostic
strings name **`CProbeUsbmuxd::DoHandshake`**. The agent *is* the host, so this
is host-side protocol logic, and decoding it converts the previously observed
byte sequence into named, validated behaviour.

**Fact:** The decode was checked against the captured WIN-START-E002 streams and
is byte-exact. Rebuilding the host side from the decoded rules reproduces the
captured outgoing startup bytes exactly; the captured incoming stream parses with
zero bytes left over; every one of the 1,903 image-record headers re-encodes to
its captured bytes; and the whole 130,375,177-byte application stream is
accounted for with no remainder. This validation used no device and no Windows.

Names below are the vendor's, taken from its format strings, not invented:
`supported network byte order`, `send network byte order failed`,
`type_net = 0x%d, len_net = 0x%08X`, `hello ack`, `hello ack unknown type`,
`ready ack unknown type`, `client resolution (%d, %d) -> (%d, %d)` and
`recv extra data length failed`.

## The exchange

| Step | Direction | Bytes | Established meaning |
| --- | --- | --- | --- |
| 1 | host → device | `04 00 00 00` | Byte-order probe. RVA `0x3046e` stores the literal DWORD **4** and sends 4 bytes — an integer, not a header. |
| 2 | device → host | 4 bytes | RVA `0x304d2` compares **byte 0 only** against 4. Success logs `supported network byte order` and sets network-order mode. |
| 3 | host → device | `05 00 00 0c` + `00000001 00000000 00000000` | HELLO: control record, field 0 = 1. |
| 4 | device → host | 16 bytes | HELLO ACK. RVA `0x305f6` **requires field 0 == 2**; field 1 is the client width, field 2 the height (RVA `0x30659`–`0x3067c`). Observed 2048 × 1536. |
| 5 | host → device | `05 00 00 0c` + field 0 = `0xfe` | READY. |
| 6 | device → host | 16 bytes | READY ACK. RVA `0x30748` **requires field 0 == 0xff**. |
| 7 | host → device | `05 00 00 0c` + field 0 = `0xfc`, field 1 = `05 00 00 00` | Precedes the trailing "extra data" block. See the mixed-endianness note. |
| 8 | device → host | 4-byte header, then a looped body read | "Extra data": the generic variable-length reader. |
| 9+ | host → device | tag 6 records | JPEG image stream, 1,903 records (WIN-START-E005). |

## Record format

**Fact:** The header is a type byte followed by a 24-bit big-endian payload
length. The agent builds the header word as `(htonl(len << 8) << 8) | type` at
RVA `0x3055f`–`0x30562` and stores it little-endian, which places the type in
byte 0 and the length big-endian in bytes 1–3. It reverses exactly that at RVA
`0x3087b`–`0x3089e`: mask the type byte off, byte-swap, shift the type back in,
take the top 24 bits as the length. Written plainly the header is
`[type, len>>16, len>>8, len]`. This independently re-derives the FED-FRAME /
WIN-START-E005 framing rule from the construction side rather than from observed
bytes.

**Fact:** Control-record payloads are three 32-bit fields. Each passes through
`htonl` in network-order mode (RVA `0x30570`/`0x3057e`, `0x306be`/`0x306cf`,
`0x30806`/`0x30817`) and is stored natively otherwise.

## Mixed endianness in the `0xfc` record — now explained

**Fact:** WIN-START-E005 noted that the `05 00 00 00` bytes in the final host
message "need independent interpretation" and that the field was written
little-endian. The instructions explain it: at RVA `0x30829` field 1 is written
as a plain `mov` of the literal **5** with **no `htonl`**, unlike every sibling
field in the same record and unlike every other field in the exchange. So field 0
goes out big-endian `0xfc` while field 1 goes out little-endian `5`. This is an
inconsistency in the vendor's own code, and a host must reproduce it to match the
wire. `hashi_startup.encode_control` exposes it as the explicit `raw_field1`
flag, with a test asserting that *not* using it fails to match the capture, so
the quirk cannot be "tidied away" by accident.

**Hypothesis:** the 5 may be a protocol or feature version. RVA `0x307d6` calls a
helper at `0x2cda0` which resolves `RtlGetVersion` from `ntdll.dll` via
`GetModuleHandleW`/`GetProcAddress` into a 0x11c-byte buffer (the size of
`RTL_OSVERSIONINFOEXW`) and the caller requires the result `>= 5` before sending.
The gate constant and the sent constant are both 5, which is suggestive but
**not** proof: the gate reads an OS version and the sent value is a separate
literal. Do not record this as established.

## Byte-order mode and the legacy fallback

**Fact:** The probe result is carried in a local flag and written to shared state
**`+0x40`** at RVA `0x307a6`. That identifies `+0x40`, previously documented only
as a "header representation flag in the inspected send path": it is **1 when the
byte-order probe succeeded** and 0 otherwise.

**Fact:** When the probe fails — send short, receive short, or reply byte 0 not 4
— control reaches RVA `0x30539`, which sets the record type to **1** instead of
5 and leaves every field in native order. So a complete legacy native-order
variant of the same exchange exists in the binary.

**Limitation:** that fallback was decoded but **never observed on the wire**. The
captured session negotiated network byte order successfully. Treat the fallback
as implemented-by-the-vendor, not as validated behaviour.

## Client dimension alignment

**Fact:** Before storing the client dimensions the agent aligns them:
`((value - 1) & ~3) + 4`, at RVA `0x30783`–`0x3078c` for the width into shared
`+0x14` and `0x30792`–`0x3079b` for the height into `+0x18`. It logs the pair as
`client resolution (%d, %d) -> (%d, %d)`. Note this is **not** a plain round-up:
a value already a multiple of 4 passes through unchanged. The observed 2048 and
1536 are both already aligned, which is why the capture shows no change and why
the alignment was not visible from the bytes alone.

## Lengths, timeouts and the receive split

**Fact:** Every send must return exactly the requested length, and every fixed
read exactly 16 bytes (`cmp edi,0x10` at RVA `0x3059c`, `0x305d4`); anything else
takes a failure path. Receives go through helper `0x4112d0` with the timeout in
ECX: **5000 ms** (`0x1388`) for the fixed exchanges, **500 ms** (`0x1f4`) for the
final 4-byte header, and **300 ms** (`0x12c`) per body chunk, with the body loop
abandoning once its counter exceeds 10.

**Fact:** The final message is read as a 4-byte header, then a `length + 1` heap
allocation at RVA `0x308ca`, then a loop receiving until the announced length
arrives. A zero length is rejected with `recv extra data length failed`. **This
explains an earlier open observation:** WIN-START-E002 recorded that the last
16-byte reply arrived as a 4-byte receive followed by a 12-byte receive, and
treated it as evidence that API boundaries are not message boundaries. That
remains true, but the split is now known to be **by design** — the agent itself
issues a header read and then a body read for this message — not a network
artifact.

## The trailing "extra data" block is a JSON capability document

**Fact:** RVA `0x309a0`–`0x30ac5`, still inside `CProbeUsbmuxd::DoHandshake`,
feeds the received block to a **JSON** parser and logs
`parse extra data failed, %s` (VA `0x5ab090`) on failure. The parser is JsonCpp
or a close relative: its error strings sit verbatim in `.rdata`, including
*"A valid JSON document must be either an array or an object value."*,
*"Syntax error: value, object or array expected."* and
*"Missing ':' after object member name"*.

**Fact — the differential-JPEG gate, at last.** The agent inspects exactly one
key, `diff_jpeg` (VA `0x5ab0b4`), through a three-step chain, each step falling
straight through to "disabled":

1. the document **contains** the key (RVA `0x30a40`);
2. that member **is a boolean** (RVA `0x30a57`);
3. its value **is true** (RVA `0x30a6e`).

Only then does RVA `0x30a83` store **1** into shared `+0x68` and log
`enable jpeg diff stream` (VA `0x5ab0c0`). Otherwise RVA `0x30aa8` stores 0. Per
the established field table, `+0x68` selects differential JPEG when `+0x64` is
zero — so this is the whole negotiation.

**This explains the observed encoder choice.** The captured extra-data body is
the 12 bytes `00 00 00 fd 00 00 00 00 00 00 00 00`, read as a 4-byte header plus
body. It begins with NUL and is not a valid JSON document, so the parse fails,
`+0x68` stays 0, and **ordinary JPEG is selected** — exactly the runtime
`CEncoderVideoJpeg` at vtable RVA `0x1ac818` that WIN-BACKEND-E003 observed. The
long-standing question of why ordinary rather than differential JPEG ran is
answered: the device never advertised the capability in a form the agent accepts.

**Note on an earlier wording.** WIN-START-E005 recorded that the captured
capability body "bypasses the inspected `diff_jpeg` key path". That is now
precise: the body does not reach the key test at all, because the JSON parse
fails first. The conclusion was right; the mechanism is now established.

**Limitation:** a successful parse with `diff_jpeg: true` has never been
observed, so the differential-JPEG *path itself* remains unexercised. Knowing how
it is enabled is not the same as knowing what it then sends. `hashi_startup`
implements the gate, not the codec.

## Implementation

`hashi_startup.py` implements the above and is validated by
`tests/test_hashi_startup.py`. It is a **codec**: it builds and parses byte
strings, performs no I/O, opens no socket and talks to no device. Reproducing the
observed bytes offline is its purpose. The existing `hashi_framing.py` is reused
unchanged for the image-record portion.

## Limitations

- Established for **one** captured session in network-byte-order mode.
- The legacy native-order fallback is decoded but unobserved.
- The meaning of the `0xfc` record's literal 5 is **not** established.
- Tag values other than 4, 5 and 6; all error, timeout and reconnection paths;
  session shutdown; and every operating mode other than the captured one remain
  unestablished. (Input events are covered by FED-STREAM-E001.)
- The differential-JPEG path is never exercised: the gate is established, but no
  session has enabled it, so what it transmits is unknown.
- Nothing here authorises transmitting these bytes to an iPad. That is a separate
  decision the user has not taken, and no code in this repository does it.
