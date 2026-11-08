# HASHI continuation prompt

Copy the prompt below into the next model's session. It assumes the same working
directory, repository and private evidence remain available. **Inspect the actual
Git state rather than inventing a commit hash or assuming later edits are absent.**

---

Continue HASHI in `/home/noobiegg/Documents/github-stuff/hashi` on Fedora.
Preserve the current repository, private evidence and working Windows
installation. Read any applicable repository instructions, inspect `git status`,
the branch, remotes and recent commits, then read
`docs/fedora-mode-selection.md`, the top of `docs/fedora-startup-validation.md`,
the top of `docs/fedora-next-steps.md` and the top of `RETURN-TO-WINDOWS.md`.
`docs/windows-startup-framing.md` holds the existing capture boundary and
`docs/fedora-backend-import.md` the import receipt. Label meaningful conclusions
**Fact**, **Inference** or **Hypothesis**, and keep evidence IDs, hashes, UTC
timestamps, RVAs and limitations.

## Completed work: do not restart it

- The Windows capture, framing and image validation are complete:
  WIN-START-E001–E005 and FED-FRAME-E001. 1,903 tag-6 JPEG records, exact
  record boundary, twelve decoded pixel-matched samples.
- The live REA/Ghidra study check is complete and **must not be repeated**; the
  study DLL must not be rebuilt.
- The Windows backend observation is complete: WIN-BACKEND-E001–E004. The live
  captor was **LCI** (vtable RVA `0x1ac4b4`) and the encoder was **ordinary
  JPEG** (vtable RVA `0x1ac818`). `InitCaptor`'s failed-initialization fallback
  is **StVD** (`0x37f10`), correcting the older OSBase claim.
- The mode-selection chain is traced: **FED-MODE-E001**. See below. Do not
  re-derive it.
- The 2026-11-07 backend transfer is imported and fully verified (138 payloads,
  98 indexed files, bundle fast-forwarded to `4193abc`). The archive was
  deleted after verification; do not look for it.

## What FED-MODE-E001 settled

**Fact:** The output dimensions reaching ordinary JPEG initialization are the
selected monitor's `rcMonitor` extent from `GetMonitorInfoW` — record append
`0x3ca00` stores `right - left` at record `+0x10` and `bottom - top` at `+0x14`;
getters `0x3cde0`/`0x3ce50` feed shared `+0x1c`/`+0x20`. The LuminonCore
rectangle `[1920,0,3200,960]` gives exactly the observed 1280×960. The captor
reads the mode; it does not request it.

**Inference:** `CCaptor::CustomizeResolution` `0x32590` and `RestoreResolution`
`0x32830` are the captor's only `ChangeDisplaySettingsExW` paths and both require
`shared[+0x44] != 0`, while the LCI rung requires `+0x44 == 0` and `MirrorMode`
was 0 — so they cannot have set the mode. `CMultiDisplay::FindBestResolution`
`0x42530`, reconstructed from instructions, selects 1600×1200 rather than
1280×960 for this client.

**Fact:** The mode was already 1280×960 at `16:15:46Z`, before the
`16:17:54Z`–`16:19:55Z` trace window. A reconnect that starts with the display
already attached contains no mode decision to observe.

**Fact (user-reported):** the 1280×960 mode was the **user's own choice** in
Windows display settings — the size they want for the iPad — persisted by Windows
for `LCI\IDDCX`. **The sizing question is closed and needs no Windows access.**
Do not plan a registry check, a persisted-mode check, an attach transition or any
instrumentation for it. `ForceResW`/`ForceResH` stay unqueried but cannot matter
(`CustomizeResolution` needs `MirrorMode != 0`; LCI needs `MirrorMode == 0`).

**Still open, all answerable offline:** where `AttachExtendDisplay`'s requested
size comes from; the unclassified `ChangeDisplaySettingsExW` sites; the
enumerator's ordering contract; whether the reconstructed score formula is
numerically exact.

## Private evidence and identity

Let `D` be `/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z`
and `B` be `/home/noobiegg/HASHI-private/imports/backend-20261107-20261107T170633Z`.

- `D/bundle` holds the original verified Windows evidence (1,993 files, 512
  directories) plus the agent and study DLL. Do not alter, replace or clean it up.
- `B/bundle` holds the 2026-11-07 transfer: `private-evidence/backend-20261106`
  with its verified 98-file `evidence-index.json`
  (SHA-256 `f9fcdb8493d4dd8c30c6827b660ab7cf01d87e5d9171ef6cd1f4e5b29fd8981b`),
  the retained **failed** first probe, raw traces and receipts.
  `B/import-verification-receipt.json` records the whole import.
- `B/analysis/mode-chain-20261107T171124Z` is the FED-MODE-E001 run; its
  `evidence-index.json` has SHA-256
  `d107f65f6638bc2a6eefb09a7f16738979fdc5d3f6dcca8325396f90fccfe153`. It holds
  the focused asm extracts, the full private disassembly and the score
  reconstruction. Read it before repeating any static work.
- Agent: `D/bundle/private-evidence/windows-runs/20261031-184820/binaries/SWXDAgent.exe`,
  SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`,
  `pei-i386`, preferred base `0x400000`. **Never execute it.** Static
  disassembly with `objdump` on Fedora is how it has been read so far.
- Study DLL: `D/bundle/.../study-build/ex06_hashi.dll`, SHA-256
  `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. Preserve;
  do not rebuild.

Private directories are 0700 and files 0600. Do not stage binaries, raw
captures, decompiler output, receipts or instrumentation artifacts; `.gitignore`
covers `/hashi-stuff/`, `__pycache__/` and `*.pyc`, and private evidence lives
entirely outside the checkout. Create a fresh private run directory for new work
rather than writing into an existing one.

## Repository code

`hashi_framing.py` is the validated record-boundary and JPEG-header parser;
`hashi_startup.py` the handshake codec and capability gate; `hashi_stream.py` the
steady-state codec, input mapping and event dispatch; `hashi_gnome.py` the verified Mutter virtual-monitor and input-injection layer (FED-DBUS-E001, never executed); `hashi_host.py` the composition of all of it (also never executed); `hashi_mode.py` holds the
FED-MODE-E001 dimension rules, with the reconstructed
`FindBestResolution` scorer clearly marked **Inference** and deliberately not
wired into anything. `hashi_jpeg.py` holds the frame prelude and the encoder, and
`hashi_usbmux.py` the transport. Tests live in `tests/`, which has no
`__init__.py`, so bare `unittest discover` fails; run them with

```sh
python3 -m unittest tests.test_hashi_framing tests.test_hashi_mode \
  tests.test_hashi_startup tests.test_hashi_stream tests.test_hashi_jpeg \
  tests.test_hashi_usbmux tests.test_hashi_gnome tests.test_hashi_host
```

261 tests, passing. Reuse these rather than rewriting them.

## What FED-START-E001 settled

**Fact:** `CProbeUsbmuxd::DoHandshake` at RVA `0x303f0` is decoded in full and
implemented in `hashi_startup.py`. Header = type byte + BE24 length, built as
`(htonl(len << 8) << 8) | type`. Step 1 is a little-endian DWORD 4 byte-order
probe; only byte 0 of the reply is checked; the result lands in shared `+0x40`.
HELLO/HELLO ACK/READY/READY ACK require field 0 = 1/2/0xfe/0xff. Client
dimensions come from HELLO ACK fields 1 and 2, aligned `((v-1) & ~3) + 4` into
shared `+0x14`/`+0x18`. The `0xfc` record's field 1 is written with **no**
`htonl`, which is why it appears little-endian. The final reply is read as a
4-byte header then a looped body, so its 4-plus-12 split is by design.

**Fact:** Validated offline with no device and no Windows — byte-exact outgoing
startup, zero-remainder incoming parse, all 1,903 image headers re-encoding, and
the whole 130,375,177-byte application stream accounted for.

**Do not promote these:** the `0xfc` literal 5 is a **Hypothesis** (a nearby gate
wants an `RtlGetVersion`-derived value `>= 5`, which is suggestive, not proof),
and the legacy native-order fallback (type 1) is decoded but **never observed**.

## What FED-STREAM-E001 settled

**Fact:** `CConnectBase::Run` (RVA `0x2f580`) and `CConnectBase::ReceiveThread`
(RVA ~`0x2f8c0`) are decoded, in `hashi_stream.py`. The **whole outgoing
application stream reproduces byte-for-byte** (130,375,177 bytes, SHA-256
`85b81dd7e307b371e45be5dda6eb26bfc35c3fe789af1c32ec2a70413a2cb123`). Same header
codec as startup, third independent confirmation. Pacing `1000 / fps` off
`GetSystemTime`'s `wMilliseconds` only, so it wraps every second. Outbound sends
are checked only against `SOCKET_ERROR`, not length — a host should check properly.

**Fact:** inbound TLV is the **input** channel: handler `0x440110` builds a
28-byte Win32 `INPUT` and calls `SendInput`; its 17-entry table at VA `0x4404f8`
is mapped. `SendReconfigVideo` sends field 0 = 1 with the output dimensions from
shared `+0x1c`/`+0x20`, swapped when `+0x24` is set; field 0 = 1 is the same
value the startup HELLO uses, so resize is decoded, not guessed.

**The governing limitation:** the captured incoming stream is 346 bytes — 294
usbmux, 52 startup, **zero** steady state. No inbound record, no reconfiguration.
The input dispatch and reconfig encoder have **no** byte-exact validation. Do not
promote them, and do not assign meanings to `field0` values or coordinates.

## What the 2026-11-08 offline continuation added

**Fact:** input event kinds are mapped. The six 7-byte stubs set exactly the
Win32 `MOUSEEVENTF_*` button constants (5/6 left down/up, 8/9 right, 14/15
middle); 4 and 7 are movement-only; 1 and 2 are keyboard; 3, 11, 12, 13 are
accepted and ignored; 16 and 17 go to `CInput::ProcControlMessage`.

**Fact:** coordinates are Win32 absolute over the **virtual desktop**, flags
`0xC001`, normalised by the constant 65535.0. Full transform:
`((value + monitor_origin - desktop_origin) / desktop_span) * 65535`, with the
monitor origin from record `+0x00`/`+0x04` (RVA 0xcd00/0xcd70). **Incoming
coordinates are monitor-relative pixels**, so a host must know its display's
placement in the desktop.

**Fact:** input is three subsystems — mouse and keyboard via `SendInput`,
multi-touch via `InitializeTouchInjection`/`InjectTouchInput` with a
`ContactID`, and `CInput::HandleHidMessage`.

**Fact:** the handshake's trailing extra-data block is a **JSON** document. The
`diff_jpeg` gate is: key present, member is a boolean, value true → shared
`+0x68` = 1. The captured body (`000000fd` + zeros) is not valid JSON, so the
parse fails and ordinary JPEG is selected — **this explains the observed
`CEncoderVideoJpeg`**, closing a question open since the first capture.

**Fact:** `CConnectBase::HandleEvent` accepts ids 2..202 and handles exactly
five (2, 4, 26, 201, 202); TLV `0x70` enqueues id `0xc9` = 201.

**Still unobserved:** every inbound record. The differential-JPEG path is gated
but never enabled, so what it transmits is unknown.

## FED-LIVE-E001: the host now works against the real iPad

**Fact:** on 2026-11-08 the user granted explicit authority for device contact
and the probe succeeded. The decoded handshake completed first time; 362 replayed
1280x960 frames (9.6 MB, 30 fps) were **displayed on the iPad**, user-confirmed;
and a 45-second window captured **1,449 inbound input records**.

**Fact:** the handshake's client dimensions (2048x1536) and 12-byte extra-data
block (`000000fd` + zeros) are byte-identical to the Windows capture, confirming
the `diff_jpeg` gate's real-world outcome: ordinary JPEG.

**Fact:** every inbound record was TLV type 7, 16 bytes, `07 00 00 0c` header,
big-endian payload, zero truncation, coordinates inside the 1280x960 display's
pixel space. `field0` **5 = pointer down, 6 = up, 10 = motion**; downs and ups
strictly alternate, a tap is `5 -> 6`, a drag is `5 -> 10... -> 6`. Static
analysis had predicted 5 and 6 from the `MOUSEEVENTF_*` constants alone; 10 was
the one value it could not classify.

**Frames were replayed, not generated.** The user recognised the **Windows
desktop UI** from the original capture on the iPad screen, which confirms the
frames decoded faithfully rather than merely being accepted — and makes the
replay unmistakable as a replay. Transport, handshake, framing and frame format
are validated. Frame *generation* is not.

**Still unexercised:** multi-touch and the `ContactID`/`InjectTouchInput` path,
keyboard (`field0` 1/2), `field0` 16/17, reconfiguration, the TLV `0x70` subtype,
and differential JPEG.

## FED-DBUS-E001: the Mutter contracts are verified and the GNOME layer is built

**Fact.** Every `ScreenCast` and `RemoteDesktop` signature is verified against
the installed `mutter-51.1-1.fc45` build, three ways: live introspection of the
two top-level interfaces, the `GDBusMethodInfo`/`SignalInfo`/`PropertyInfo`
tables recovered from `libmutter-51.so.0`, and the Fedora source RPM, which
applies **no patches** and so matches the running binary. This closes the
caveat that only the method *names* were known. **No session was created.**
See `docs/fedora-mutter-dbus-contracts.md`; private run
`fedora-dbus-20261108T042538Z`, index SHA-256
`57d954b908f06dbeb04fac047c7ddd6cf0a97ad06091190fbdac65dd147b8c84`.

**Fact — the sizing question is settled in HASHI's favour.** `RecordVirtual`
accepts a `modes` (`aa{sv}`) key: "If set, the PipeWire stream becomes
non-resizable, and size is controlled by the compositor as if it was a regular
monitor." Each mode takes `size` (`(uu)`, required), `refresh-rate` (`d`) and
`is-preferred` (`b`), exactly one preferred. So **1280×960 can be pinned** rather
than negotiated. This *corrects a hypothesis*: negotiating the size through the
PipeWire format is real, but it is the fallback path taken only when `modes` is
absent.

**Fact — `NotifyPointerButton`'s `button` is an evdev code**
(`meta_evdev_button_to_clutter`), so `BTN_LEFT` = 272, not a `MOUSEEVENTF_*`
flag and not a Clutter button number. The XML does not say this; the
implementation does. `NotifyKeyboardKeycode` is likewise an evdev keycode.

**Fact — the coordinate simplification is confirmed**, now from the
implementation rather than the method name. For a virtual stream the whole
transform is `*x = stream_x + view_layout.x` (same for y): a pure translation by
the monitor's stage position, no scaling, no normalisation. The iPad's
monitor-relative pixels go straight in as doubles. **Do not reimplement the
Windows 65535 virtual-desktop transform; it has no Linux counterpart.**

**The operational trap:** `transform_position` returns FALSE until the stream
has a `ClutterStageView`, and the caller then logs "Dropping early absolute
pointer motion" and **completes the call successfully**. A successful D-Bus
return is therefore not proof that an event was delivered.

**Fact:** `hashi_gnome.py` implements this — the properties builders, the
`field0` → evdev/absolute-motion injection plan, and a `VirtualDisplaySession`
that is **inert on import and has never been executed**. 57 tests, 197 in all.
`pipewiresrc` is present and instantiable (it ships in `pipewire`, not
`gstreamer1-plugin-pipewire`, which is not installed and not needed), so
`pipewire-devel`'s absence does not block capture.

**Pinned to a GNOME version range.** These are Mutter's private APIs; the XML
states "no compatibility between versions are promised". The verification holds
for 51.1 only, and `check_versions` refuses anything else.

## Next task, in order — there is no pending Windows work

## FED-HOST-E001: the host works end to end — do not re-prove it

**Fact (2026-11-08).** The iPad displayed frames HASHI **generated** from a
real Mutter virtual monitor, and touches moved the **Linux** pointer. Pinned
1280x960 negotiated exactly; handshake returned the usual 2048x1536 /
`diff_jpeg=False` (third identical confirmation); a 30 s run gave **1,540
inbound records -> 1,540 injected** and **820 damage-driven captures** — a
static virtual monitor is never damaged, so 820 captures is the system's own
proof the pointer was moving. ~26.5 fps at ~372 KB/frame (~10 MB/s).
See `docs/fedora-host-live.md`; run `fedora-host-20261108T080007Z`, index
SHA-256 `669db3bf4578aff81d4a8bcd878cbc2706f18da8138414b9e79c65b41088de12`.

**THE TRAP — read before touching the input path.**
`NotifyPointerMotionAbsolute` is **silently discarded until something is
consuming the PipeWire stream**, while the D-Bus call returns success.
`NotifyPointerButton` has no stream argument and no transform, so it lands
regardless: the symptom is **clicks at a stale pointer position — selected
text, windows behaving oddly — with a pointer that never moves**, and no error
anywhere. Measured with Mutter's idle timer: 40 motion calls took idle
14,741 -> 15,605 ms (climbing) with no consumer, and 20,683 -> **21 ms** with
one. `VirtualDisplaySession.inject` now refuses unless `stream_consumed`.

**Correction to FED-DBUS-E001:** do **not** assert geometry via
`Stream.Parameters`. A virtual stream exposes only `mapping-id` —
`set_stream_parameters` has branches for monitor/area/window and none for
virtual, and runs before the monitor exists. Assert the negotiated PipeWire
caps instead; the pipeline pins them, so a wrong size fails negotiation.

**Other facts the first run established:** the stream negotiates
`framerate=0/1` (damage-driven), so an idle monitor yields **no** buffers and
the host must repeat its last frame rather than treat a timeout as an error;
and usbmuxd **reassigns `DeviceID` on every attach**, so it must be discovered
via `ListDevices` — a hard-coded `1` failed the next session with
`BADDEV (Number=2)`.

## Next task, in order — there is no pending Windows work

1. **Efficiency.** Every frame is re-sent in full (~372 KB) even when nothing
   changed. Not re-sending an unchanged frame is the obvious saving; the
   protocol's `diff_jpeg` path exists for this but the device gates it off and
   it was never observed, so it cannot be implemented.
2. **Assert, don't assume, the captured size.** Check the PipeWire buffer is
   1280×960 and that `Stream.Parameters` reports `size = (1280, 960)`. The JPEG
   prelude hard-codes that size, and if the virtual monitor ends up scaled, the
   logical coordinates injection uses and the buffer's pixels diverge.
4. **The indirect vtable targets** behind the five `HandleEvent` cases, if the
   `0x70` subtype ever matters.
2. **`field0` 10's path**, the 16/17 `ProcControlMessage` body that reads
   `field2` as two packed 16-bit halves, the touch-injection path and its
   `ContactID` handling, and `CInput::HandleHidMessage`.
3. **JPEG emission**, and the `CEncoderVideoSRx264` alternative codec
   (`SRx264Wrapper.dll`, selected by shared `+0x64`, entirely unexercised). All
   1,903 frames share one DQT/DHT table set and 4:2:0 sampling, so a host can
   emit the same tables without guessing. Target size is **1280×960**.
4. `AttachExtendDisplay` callers and the unclassified `ChangeDisplaySettingsExW`
   sites, to bound the FED-MODE-E001 claim by evidence.
5. Reconcile new evidence with explicit Facts, Inferences and unknowns. Keep
   extending the offline byte-exact harness rather than reaching for the device.

**The one thing that needs hardware:** observing inbound input records requires
the iPad connected *and* someone touching its screen while a capture runs. The
user has been asked about this; do not assume it has happened.

## Constraints

Do not execute transferred Windows binaries. Do not change drivers, display
settings, pairing or the vendor installation. Do not send a Fedora-side startup
replay to the iPad — the user declined that path. Do not implement guessed
handshake, resize, codec or control messages. Do not repeat a cable cycle to
re-prove framing, transport or the study check. Do not push without explicit
instruction; no push has been requested, and `refs/backup/pre-backend-import-20261107`
retains the pre-import head.
