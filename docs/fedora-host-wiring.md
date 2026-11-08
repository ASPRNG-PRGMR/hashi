# The host composition — design, not evidence

2026-11-08. `hashi_host.py` is the loop that ties the project's layers together:
captured desktop → JPEG frames → the validated transport, and inbound records →
pointer injection.

**This report carries no evidence ID, deliberately.** Every other Fedora report
is named for something observed — FED-START-E001 for a byte-exact handshake,
FED-LIVE-E001 for frames on the iPad, FED-DBUS-E001 for verified contracts.
Nothing in this one has been run. The composition is a design **Inference** from
end to end, and it should keep that status until a session has actually streamed
a captured desktop to the device.

What *is* established is everything underneath it:

| Layer | Status |
| --- | --- |
| usbmux transport | validated offline, then used live (FED-LIVE-E001) |
| Startup handshake | byte-exact offline; succeeded against the device first try |
| Record framing | whole outbound direction reproduces byte-for-byte |
| JPEG frames | prelude exact 1903/1903; a black frame byte-identical |
| Input semantics | `field0` 5/6/10 observed live across 1,449 records |
| Mutter contracts | verified three ways (FED-DBUS-E001) |
| **Their composition** | **never executed** |

## Shape: pure where it can be, thin where it cannot

The module is split so that everything testable without a compositor, a device
or a socket is a pure function or an injectable object, and the live parts are
thin shells over them. `HostSession` takes its frame source and its display as
constructor arguments, so the whole loop runs in tests against a fake socket and
a solid-colour source. 52 tests cover it; 249 in the project.

### `InboundDemuxer` — the part most likely to hide a bug

A socket delivers arbitrary chunks, so records arrive split and coalesced. The
demuxer buffers bytes and yields whole records using the decoded framing: a
4-byte `[type, BE24 length]` header, then that many payload bytes.

**Fact (FED-LIVE-E001):** all 1,449 observed records were type 7 with header
`07 00 00 0c` and a 12-byte payload — 16 bytes, no truncation. So the common
case is a fixed 16-byte record. The framing is still honoured in general,
because the decode says the length is a field, not a constant.

Two decisions worth stating:

* **An overlong record is consumed in full, while only the 12 bytes the agent
  keeps are parsed.** The agent clamps what it *retains* to 12 bytes
  (RVA 0x2fb45) but still consumes what was announced. A host that both kept
  and consumed 12 would leave the remainder in the stream, and every later
  record would start mid-payload — one malformed record silently corrupting
  everything after it. Tested directly.
* **An absurd announced length is refused rather than buffered.** 24 bits allows
  16 MB; a corrupt or hostile length would otherwise stall the loop waiting for
  bytes that never come. The limit is arbitrary (4 KiB) and is a sanity bound,
  not a protocol fact.

Tested at every split point of a 16-byte record, byte-at-a-time delivery
included, plus a reassembled 22-record drag.

### `Pacer` — a deliberate divergence from the agent

**Fact:** the agent's pacing reads only `GetSystemTime`'s `wMilliseconds`
(RVA 0x2f74a–0x2f76a), so its own elapsed measurement wraps every second and
cannot distinguish a 1.2-second stall from a 200 ms one.
`hashi_stream.pacing_sleep_ms` reproduces that faithfully, wrap included,
because the point of that module is to document the agent.

A *host* has no reason to inherit it. `Pacer` takes the target interval from the
decoded `1000 / fps` rule — truncation and all — but measures with
`time.monotonic`. It also schedules against the previous *target* rather than
the previous wakeup, so a single late frame does not push every later frame
late, and a stall longer than one interval resets the schedule instead of
catching up in a burst.

This is the one place the host knowingly does not copy the agent, which is why
it is called out rather than left for a reader to notice.

### Frame sources

* `SolidColourSource` — **the known-good path.** A generated solid-black
  1280×960 frame is byte-identical to the first captured record, scan data
  included. If a live run shows nothing on the iPad, this source separates a
  frame-generation fault from a capture or transport fault, which is worth more
  than it looks: it is the only generation path with byte-exact backing.
* `ReplayFrameSource` — what FED-LIVE-E001 actually streamed. Retained because
  it is the only source already proven to put a recognisable picture on the
  device, so it is the reference when a generated frame does not.
* `PipeWireFrameSource` — the real one, and the only untried one.

### Capture

`capture_pipeline_description` builds:

```text
pipewiresrc path=<node_id> always-copy=true !
videoconvert !
video/x-raw,format=RGB,width=1280,height=960 !
appsink name=sink emit-signals=false max-buffers=1 drop=true sync=false
```

`node_id` is what `Stream.PipeWireStreamAdded` hands back and what
`pipewiresrc`'s `path` property wants. The caps are pinned to the virtual
monitor's own mode so a mismatch fails in negotiation rather than quietly
producing wrong-sized frames. `videoconvert` is unconditional because the
compositor's buffers are typically BGRx while Pillow needs RGB.
`max-buffers=1 drop=true` keeps the loop on the newest frame — correct for a
display, where latency matters and completeness does not.

**`pipewiresrc` is present and instantiable** (FED-DBUS-E001): it ships in the
`pipewire` package as `/usr/lib64/gstreamer-1.0/libgstpipewire.so`, so
`pipewire-devel`'s absence does not block capture and
`gstreamer1-plugin-pipewire` is not needed.

## Two refusals instead of guesses

1. **A device that enables `diff_jpeg` aborts the handshake.** The gate is
   decoded and the observed device never passes it (its 12-byte block is not
   valid JSON), so ordinary JPEG is the real path. But the differential format
   itself was never observed, so a host that met an enabling device would have
   nothing to encode. Failing with a clear message beats transmitting a guess.
2. **A frame that is not 1280×960 is never sent.** The 623-byte prelude encodes
   the size in its SOF0, so a mismatch would be a JPEG disagreeing with the
   stream the device was told to expect. The buffer size is also checked against
   `width * height * 3`: GStreamer pads rows to a 4-byte stride, and although
   1280 × 3 = 3840 is already aligned, an unnoticed stride would *shear the
   image diagonally* rather than fail — the kind of fault that sends you
   debugging the protocol instead of the capture.

One place the host deliberately improves on the agent: sends use `sendall` and
check the length. FED-STREAM-E001 found the agent checks only against
`SOCKET_ERROR` and never the byte count, so a short send would silently corrupt
its stream.

## What a first run needs, and what it would prove

Both gates belong to the user, not to the code:

* **Creating the D-Bus session is user-visible** — a monitor appears and a
  screen-sharing indicator shows.
* **Sending bytes to the iPad needs fresh authorisation.** The 2026-11-08 grant
  covered that session only.

A sensible first run is in two stages, because they fail independently:

1. **No device.** Open the virtual monitor, assert `Stream.Parameters` reports
   `size = (1280, 960)`, capture a handful of frames, check each is 1280×960 and
   encodes. This validates the GNOME half alone, and the assertion matters: if
   the compositor applies a scale, the logical coordinates injection uses and the
   buffer's pixels diverge, which the pure translation in
   `meta_stream_transform_position` would otherwise hide.
2. **With the device.** Stream `SolidColourSource` first — the known-good frames
   — then the live capture, then touch the screen and confirm the pointer moves.

Only stage 2's last step exercises injection, and nothing short of a real run
can: `transform_position` returns FALSE before the stream has a view, and the
handler then logs "Dropping early absolute pointer motion" and **returns
success anyway**. So a host cannot learn from the D-Bus reply whether its events
landed. Watching the pointer is the test.

## Still unexercised, unchanged by this work

Multi-touch and the `ContactID`/`InjectTouchInput` path, keyboard (`field0`
1/2), `field0` 16/17, reconfiguration (`SendReconfigVideo`), the TLV `0x70`
subtype, and differential JPEG. `field0` values 3, 4, 7, 8, 9 and 11–17 have
never been seen on the wire. This module handles 5, 6 and 10 — the three values
that were observed — and injects nothing for the rest rather than inventing
behaviour for them.
