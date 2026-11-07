# Steady-state loop decoded — FED-STREAM-E001

Static continuation on Fedora, 2026-11-08. Target: the unchanged agent SHA-256
`cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`, `pei-i386`,
preferred base `0x400000`. All addresses are module-relative **RVAs**. Tool: GNU
objdump 2.47.20260726, static disassembly only — the target was never executed
and nothing was transmitted to the iPad. Private analysis run index SHA-256
`92cec57a335824146171970d8a7f316a268314b17b080d81cdf40b9090bf17ca`.

## Read this first: the two halves have very different standing

**The outbound half is Fact, validated byte-for-byte.** Re-encoding every one of
the 1,903 captured image records and prepending the rebuilt handshake reproduces
the **entire 130,375,177-byte outgoing application stream exactly**, SHA-256
`85b81dd7e307b371e45be5dda6eb26bfc35c3fe789af1c32ec2a70413a2cb123` on both the
rebuilt and the captured bytes. The host→device direction is now completely
reproducible offline.

**The inbound half has zero wire observations.** The generation-3 incoming stream
is 346 bytes in total: 294 bytes of usbmux control exchange, 52 bytes of startup,
and **nothing after that**. No steady-state record was ever received in the
captured session. Everything below about TLV types 3 and 7 and subtypes
`0x70`/`0x71` is read out of instructions and has never been seen on the wire.
Do not treat it as validated protocol, and do not infer what the fields mean.

## Names come from the agent, not from us

The vendor's diagnostic strings identify the whole steady state:

| String | Address |
| --- | --- |
| `CConnectBase::Run` | VA `0x5aab68` |
| `[%s] send header-length failed: %d` | VA `0x5aab7c` |
| `[%s] send data failed: %d` | VA `0x5aaba0` |
| `[%s] Bytes Sent: %ld` | VA `0x5aab0c` |
| `CConnectBase::ReceiveThread` | VA `0x5aabbc` |
| `[%s] recv tlv header error (%d,%d)` | VA `0x5aabd8` |
| `[%s] recv tlv header (0x%08X, %d)` | VA `0x5aabfc` |
| `[%s] video type(%d)` | VA `0x5aac20` |
| `[%s] type(%d), x/w(%d), y/h(%d)` | VA `0x5aac34` |
| `[%s] unknown type(%d), x/w(%d), y/h(%d)` | VA `0x5aac54` |
| `[%s] ReceiveThread exit: stoc(%d), sfd(%d)` | VA `0x5aac7c` |
| `[%s] captor(%d), fps(%d), quality(%d)` | VA `0x5aab40` |
| `CConnectBase::SendReconfigVideo` | VA `0x5aaac8` |
| `CConnectBase::HandleEvent` | VA `0x5aaa94` |
| `CProbeADB::DoHandshake` | VA `0x5aacf0` |

The last one is incidental but worth noting: an **ADB** handshake sibling exists
alongside `CProbeUsbmuxd::DoHandshake`, i.e. the agent also speaks to Android
devices. Out of scope here, and not inspected.

## Outbound frame loop — `CConnectBase::Run`, RVA `0x2f580`

**Fact:** The header is built with *exactly the same rule* as the handshake —
`(htonl(len << 8) << 8) | type` in network-order mode and `(len << 8) | type`
natively — gated on the same shared `+0x40` flag, at RVA `0x2f6c5`–`0x2f6ee`.
That is the third independent place this one codec appears (startup send,
steady-state send, steady-state receive), which is strong evidence it is *the*
framing rule rather than an artifact of one path.

**Fact:** The socket comes from shared `+0x4`. A frame goes out as **two** sends:
4 header bytes at RVA `0x2f702`, then the payload at RVA `0x2f718`. Over a byte
stream those are indistinguishable from one contiguous buffer, which is why the
captured stream parses as adjacent records. Success is logged as `Bytes Sent`.

**Fact, and a latent defect worth recording:** both sends are checked **only**
against `SOCKET_ERROR` (`cmp eax,0xffffffff` at RVA `0x2f708` and `0x2f71e`) and
**not** against the requested length — unlike the handshake, which requires exact
counts. A partial send would go unnoticed by the agent. In the captured session
every accepted length equalled the requested one, so this never manifested, and
WIN-START-E005's finding that header lengths matched accepted send lengths still
holds. A host should check properly rather than copy this.

**Fact — frame pacing:** RVA `0x2f73f`–`0x2f76a` calls `GetSystemTime`, uses
**only** its `wMilliseconds` field, computes `elapsed = current - previous` with
`+1000` applied when that goes negative, divides `1000 / fps` for the target
interval, and `Sleep`s the remainder only when the elapsed time is smaller.

**Inference:** because the measurement uses a single `wMilliseconds` field, the
agent's own elapsed calculation wraps every 1000 ms and cannot distinguish an
interval longer than a second from a short one. That is tolerable at the observed
rates and is reproduced faithfully in `hashi_stream.pacing_sleep_ms`.

**Limitation:** the configured `fps` and `quality` were not captured, though the
`InitCaptor` log shows both exist. The observed send-start intervals — median
19 ms, p95 31 ms, max 51 ms (FED-FRAME-E001) — are consistent with a target in
roughly the 16–33 ms band, i.e. fps somewhere around 30–60. That narrows the
value; it does not fix it.

## Inbound TLV loop — `CConnectBase::ReceiveThread`, RVA ~`0x2f8c0`

**Static only. Never observed. See the warning above.**

**Fact:** The loop polls the socket from shared `+0x4` through helper `0x411180`
with a **3000 ms** timeout (RVA `0x2f907`, `0x2fa4c`), then `recv`s exactly 4
header bytes at RVA `0x2f921`. A return of 0 is treated as a graceful close
(status `-11`); anything other than 4 logs `recv tlv header error` and leaves the
loop. The header is decoded with the same type-byte + BE24-length codec, gated on
shared `+0x40`, at RVA `0x2f9d9`–`0x2fa02`. The announced length is then heap
allocated at RVA `0x2fa06` and filled by a bounded receive loop.

**Fact:** Only **two** types are dispatched — **3** and **7** (RVA `0x2fae0`,
`0x2fae5`). Every other value reaches the `unknown type(%d), x/w(%d), y/h(%d)`
log and is otherwise ignored.

**Fact:** Accepted records are copied into a ring of **64 slots of 12 bytes**,
indexed modulo 64 (RVA `0x2fb1e`–`0x2fb2f`), and the announced payload length is
**clamped to 12 bytes** at RVA `0x2fb45` — a longer record is truncated, not
rejected. So a record carries at most three 32-bit fields.

**Fact — an asymmetry not to smooth over:** RVA `0x2fb5e`–`0x2fb7f` applies
`ntohl` to all three payload fields **only for type 7**, and does so
*unconditionally* — it does **not** consult the negotiated `+0x40` flag the way
the header decode does. Type 3 payloads stay in native order. This mirrors the
mixed-endianness quirk already found in the handshake's `0xfc` record, so it
looks like a pattern in this codebase rather than a one-off.

**Fact:** Field 0 then selects an inner subtype at RVA `0x2fb84`–`0x2fb90`:
`0x70` takes its own branch, `0x71` is logged as `video type(%d)`, and anything
else is passed by value as three DWORDs to handler `0x440110` and logged as
`type(%d), x/w(%d), y/h(%d)`.

**Hypothesis, explicitly not established:** the log name `x/w` and `y/h` shows a
field read as either an x coordinate or a width depending on context, which is
what one would expect of a combined pointer-input and resize channel. **Which
type or subtype means which is unknown.** The fields are named `field0/1/2` in
code for that reason. Do not promote this, and do not implement any input or
resize message on the strength of it.

## Implementation

`hashi_stream.py`, with `tests/test_hashi_stream.py`. It performs no I/O, opens
no socket and talks to no device. `hashi_framing.py` and `hashi_startup.py` are
reused unchanged — the outbound encoder round-trips through the existing
validated parser. Suite is 59 tests.

## What remains, and what it would cost

Answerable offline from the agent already present:

- Handler `0x440110` and the `0x70` branch, neither decoded in this slice.
- `CConnectBase::SendReconfigVideo` and `CConnectBase::HandleEvent`, which should
  show how a resize or mode change is *sent*, and may disambiguate the TLV types
  without any device.
- The trailing "extra data" block from the handshake, and the capability /
  `diff_jpeg` parser. The captured capability body begins with NUL and bypasses
  the inspected `diff_jpeg` key path, so differential JPEG remains unestablished.

**Requires the iPad connected.** Confirming the inbound TLV channel at all —
which types actually arrive, what their fields carry, and whether `0x70`/`0x71`
appear in practice — needs a session where the device genuinely sends records.
The captured run produced none, most likely because nothing touched the iPad
screen while it ran. No amount of static work can substitute for that
observation, and nothing in this repository should guess it.
