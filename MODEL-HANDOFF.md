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
steady-state codec, input mapping and event dispatch; `hashi_mode.py` holds the
FED-MODE-E001 dimension rules, with the reconstructed
`FindBestResolution` scorer clearly marked **Inference** and deliberately not
wired into anything. Tests live in `tests/` and are run with
`python3 -m unittest tests.test_hashi_framing tests.test_hashi_mode
tests.test_hashi_startup tests.test_hashi_stream` (94 tests,
passing). Reuse these rather than rewriting them.

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

## Next task, in order — there is no pending Windows work

1. **The indirect vtable targets** behind the five `HandleEvent` cases. Four end
   in `call edx` and the `0x70`-reachable case only forwards and re-tags, so the
   `0x70` subtype's purpose hinges on resolving the vtable owner — not on more of
   the same function.
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
