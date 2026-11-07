# Mode-selection call chain — FED-MODE-E001

Static continuation on Fedora, 2026-11-07. Target: the unchanged installed agent
SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`,
`pei-i386`, static preferred base `0x400000`. All addresses are module-relative
**RVAs** unless written as a VA. Tool: GNU objdump 2.47.20260726, static
disassembly only — the target was never executed, and no registry, driver or
display setting was touched on any host. Private evidence: analysis run
`FED-MODE-E001`, index SHA-256
`d107f65f6638bc2a6eefb09a7f16738979fdc5d3f6dcca8325396f90fccfe153`.

This answers the question left open by WIN-BACKEND-E003/E004: where the 1280×960
that reached ordinary JPEG initialization comes from.

## Result in one line

**The output dimensions handed to the encoder are the selected monitor's
`rcMonitor` extent from `GetMonitorInfoW` — a value the captor *reads*, not one it
requests.** The captor's own mode-setting routine is gated off in exactly the
configuration that selects LCI capture, and the agent's own best-mode scorer does
not choose 1280×960 for this client. The mode also pre-dated the traced reconnect.

## The dimension source is a monitor rectangle

**Fact:** Both monitor-refresh paths obtain output dimensions through the same
helpers, and both store them into the shared state the encoder reads:

| Step | RVA | Established behaviour |
| --- | --- | --- |
| LCI `UpdateMonitorInfo` | `0x35b30` | Calls `0x3c7a0` then `0x3c770` under a critical section, then the getters below; stores width at `0x35c4c` → shared `+0x1c`, height at `0x35c63` → shared `+0x20` |
| Generic monitor refresh | `0x324d0` | Same getters; stores width at `0x32564` → shared `+0x1c`, height at `0x3257c` → shared `+0x20` |
| Monitor-list refresh | `0x3c940` | Allocates a 0x20-byte enumerator, virtual slot `+0x10` → count, virtual slot `+0x3c` → handle per index, `GetMonitorInfoW` at `0x3c9a3` into a 0x68-byte `MONITORINFOEXW`; **if the count is zero**, falls back to `EnumDisplayMonitors` at `0x3c9db` with callback `0x3c460` (its own `GetMonitorInfoW` at `0x3c49f`) |
| Record append | `0x3ca00` | `width = rcMonitor.right - rcMonitor.left`, `height = rcMonitor.bottom - rcMonitor.top`; device name from `MONITORINFOEXW.szDevice` (`+0x28`) |
| Width getter | `0x3cde0` | Returns record `+0x10` |
| Height getter | `0x3ce50` | Returns record `+0x14` |

**Fact:** Monitor records are 32 bytes (`sar 0x5` over the vector span
`[+0x48, +0x4c)`), the selected index lives at monitor-info `+0x00` and is clamped
to `size - 1` when out of range, and both getters take a `CRITICAL_SECTION` at
`+0xa8` when the flag at `+0xc0` is nonzero. Records hold left/top/right/bottom
followed by the derived width at `+0x10` and height at `+0x14`.

**Fact (numerical corroboration):** The independently captured post-reconnect
display snapshot records `\\.\DISPLAY7`, description `LuminonCore IDDCX Adapter`,
id `LCI\IDDCX`, with monitor rectangle `[1920, 0, 3200, 960]`. Applying the
established formula gives `3200 - 1920 = 1280` and `960 - 0 = 960`, exactly the
observed shared `+0x1c`/`+0x20` of 1280×960 at encoder selection and at ordinary
JPEG initialization. The derivation and the runtime observation agree.

**Inference:** The selected-monitor index `shared[+0x70] = 1` is consistent with
`\\.\DISPLAY7`: the snapshot's `EnumDisplayMonitors` order lists `\\.\DISPLAY1`
at index 0 and `\\.\DISPLAY7` at index 1, and the agent appends records in
enumeration order. This remains an inference — the agent's preferred enumerator
object is a virtual interface whose ordering relative to the plain
`EnumDisplayMonitors` fallback is not proved.

## The captor's own mode setter cannot run in the LCI configuration

**Fact:** `CCaptor::CustomizeResolution` at `0x32590` (`thiscall`; named by the
diagnostic string at VA `0x5ab62c`) is the only `ChangeDisplaySettingsExW` path in
the captor code. It is reached from exactly one call site — `0x324db`, inside the
generic monitor refresh — and only when that function's single stack argument is
nonzero. Its gate order is:

1. shared state `[this+0x88]` non-null, else return (`0x432656`);
2. **`shared[+0x44] != 0`**, else return (`0x432660`);
3. read `HKCU\Software\Splashtop Inc.\Splashtop Wired XDisplay` DWORDs
   **`ForceResW`** (VA `0x5ab604`) and **`ForceResH`** (VA `0x5ab618`) through the
   known helper `0x2bd20` with default 0 passed in EBX;
4. require the product nonzero and `<= 0x7e9000` (3,840 × 2,160 pixels);
5. `EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, &dm)` at `0x3271f`;
6. copy the 220-byte `DEVMODEW` to `this+0xb4`;
7. overwrite `dmPelsWidth` (`+0xac`) and `dmPelsHeight` (`+0xb0`) with the forced
   values and call `ChangeDisplaySettingsExW` at `0x3275a`.

Its logs are `[%s] Change Customize resolution (%dx%d) success.` and
`... failed(0x%08x).`

**Fact:** `CCaptor::RestoreResolution` at `0x32830` (name string VA `0x5ab6bc`)
restores the `DEVMODEW` saved at `+0xb4` via `ChangeDisplaySettingsExW` at
`0x328d4`. It is gated on shared non-null, `shared[+0x44] != 0`, and both
`this[+0x160]` and `this[+0x164]` nonzero. Callers: `0x3395c`, `0x3475c`, `0x383dc`.

**Inference — the decisive point.** FED-BACKEND-E001 establishes that the LCI rung
of the `InitCaptor` ladder is taken when **`+0x44 == 0`**, and `+0x44` is the
MirrorMode field. Both routines above require **`+0x44 != 0`**. The two conditions
are mutually exclusive, and the 2026-11-06 registry snapshot recorded
`MirrorMode = 0` as a present DWORD in both the 32- and 64-bit views. So in the
observed extended-display LCI configuration neither `CustomizeResolution` nor
`RestoreResolution` can change the mode: **the captor code did not set 1280×960.**

**Limitation:** `ForceResW`/`ForceResH` are of unknown state, not known-absent.
The snapshot script queried a fixed list of eight names that excluded both, and
although it called `GetValueNames()` it did not persist that enumeration. Under
MirrorMode = 0 their value cannot reach step 4 regardless, but the reading is not
available and must not be reported as zero.

## The agent's best-mode scorer does not choose 1280×960

**Fact:** `CMultiDisplay::AttachExtendDisplay` (name string VA `0x5aceb0`) calls
`CMultiDisplay::FindBestResolution` at `0x42530` (name string VA `0x5ad414`) from
`0x4126d`, passing a requested width at `[ebp+0x8]`, a requested height at
`[ebp+0xc]` and an out-pointer, and receiving the chosen pair in object fields
`+0x8dec`/`+0x8df0`. It logs `[%s] FindBestResolution (%dx%d) -> (%dx%d)`, then
fills a `DEVMODEW` with `dmFields = 0x1c0020`
(`DM_BITSPERPEL | DM_PELSWIDTH | DM_PELSHEIGHT | DM_POSITION`) and calls
`ChangeDisplaySettingsExW` with `CDS_UPDATEREGISTRY | CDS_NORESET` (`0x10000001`)
at `0x41364`, followed by the commit call
`ChangeDisplaySettingsExW(NULL, NULL, NULL, 0, NULL)` at `0x4137a`. A sibling path
at `0x42121` uses `CDS_UPDATEREGISTRY | CDS_RESET` (`0x40000001`).
`CMultiDisplay::SetDisplayOrientation` (name string VA `0x5ad268`) is rotation
only and does not size the display.

**Fact:** `FindBestResolution` locates the adapter whose `DISPLAY_DEVICEW`
(0x348 bytes) matches the wide string **`Splashtop Virtual Video`** (VA `0x5ab3d8`)
using `EnumDisplayDevicesW` with `EnumDisplaySettingsW(ENUM_REGISTRY_SETTINGS)`,
then enumerates modes with `EnumDisplaySettingsW` from index 1 upward
(`0x425d9`, `0x42678`), discards any mode with an odd width or height, and packs
survivors as `(dmPelsWidth << 16) ^ (dmPelsHeight & 0xffff)` into an ordered set.
Each candidate is logged as `[%s] Find resolution: %d x %d`, then rescored and
logged as `[%s] Find resolution: %d for (%d,%d)[%d]`.

**Inference (reconstructed from instructions `0x427a3`–`0x42869`; not executed):**
the scorer keeps the minimum of

```text
score  = (100 * |ch*reqW - cw*reqH|) / reqH / ch      # two truncating integer divisions
       + 5 * |reqW - cw| * (cw >= reqW ? 3 : 1)
       +     |reqH - ch| * (ch >= reqH ? 3 : 1)
if (reqW/reqH == cw/ch exactly)  score /= 10          # x87 comparison, 10x bonus
```

**Inference:** evaluated over the ten modes the LCI adapter actually enumerated in
the captured snapshot, this rule selects **1600×1200** for a 2048×1536 request
(score 257) and **1600×1200** for a 1600×1200 request (score 0). It places
1280×960 third in both cases (441 and 184). It does not select 1280×960 for this
client at either candidate request size. See `hashi_mode.py` and its tests for the
executable reconstruction and these fixtures.

**Fact:** The captor sizing helper `0x31400` is a separate hardcoded
client-resolution table, not this scorer. Its observed branches include
640×480 → 1024×768, 1136×640 and 1334×750 → `0x31588`, 2208×1242 and
2001×1125 → `0x3156d`, with a default path through `0x331d0`. In the live trace it
returned 1600×1200 for client 2048×1536, which the reconstruction above
independently reproduces as the best available 4:3 mode.

## The mode pre-dated the observed reconnect

**Fact:** The display snapshot taken at `2026-11-07T16:15:46.497Z` — before the
reconnect trace window `16:17:54.080Z`–`16:19:55.773Z` — already records
`\\.\DISPLAY7` current mode 1280×960 at 60 Hz, position (1920, 0), rectangle
`[1920, 0, 3200, 960]`, and the same ten available modes including 1600×1200. The
post-reconnect snapshot at `16:19:45.408Z` is identical in all of those values.

**Fact:** The 1280×960 mode therefore already existed before the traced reconnect.
The LCI monitor refresh observed in WIN-BACKEND-E003 read an already-current mode;
it did not establish it. A probe of a reconnect that starts from an
already-attached display cannot capture the mode decision, because no decision
occurs in that window.

**Inference:** the decision belongs to an earlier display-attach event, driver
default or persisted Windows configuration for `LCI\IDDCX`. Candidate mechanisms
remain `CMultiDisplay::AttachExtendDisplay`'s `ChangeDisplaySettingsExW` pair, a
`CDS_UPDATEREGISTRY` value persisted by a previous session, or an
`IddCx`/driver-side preferred mode. This static slice does not choose between them.

## What is still unknown

- The origin of `AttachExtendDisplay`'s requested width/height; its callers were
  not resolved in this slice.
- Whether `AttachExtendDisplay` ran at all in the observed session, and with what
  request. It was not hooked, and the display was already attached.
- `ForceResW`/`ForceResH` registry state (unqueried, see above).
- The ordering contract of the agent's preferred monitor enumerator versus
  `EnumDisplayMonitors`.
- Classification of `ChangeDisplaySettingsExW` references outside the captor and
  `CMultiDisplay` clusters.
- Whether the reconstructed score formula is numerically exact on Windows. It was
  derived from instructions and validated only against the observed 1600×1200
  sizing-helper result, not against the agent's own per-candidate log lines.

## Exact evidence a later live test would need

Ordered cheapest-first. None of this is authorised or requested here; it is the
minimum that would settle the remaining question.

1. **Read-only registry enumeration.** Enumerate *all* value names and data under
   `HKCU\Software\Splashtop Inc.\Splashtop Wired XDisplay` in both the 32- and
   64-bit views and persist the enumeration. This settles `ForceResW`/`ForceResH`
   and any unknown siblings. No instrumentation, no mode change, no attach cycle.
2. **Read-only persisted-mode check.** Record the saved mode for the `LCI\IDDCX`
   device from the Windows display configuration, to test whether 1280×960 is a
   persisted `CDS_UPDATEREGISTRY` value rather than a fresh decision.
3. **An attach transition, not another reconnect.** The decision only occurs when
   the extended display goes from detached to attached. Any probe must span that
   transition, with the pre-state recorded as detached.
4. **One narrow instrumentation boundary**, if 1–3 leave it open: entry and return
   of `FindBestResolution` (`0x42530`) recording `reqW`, `reqH` and the returned
   pair; the agent's own per-candidate `Find resolution: %d for (%d,%d)[%d]` log
   output to check the reconstructed formula; and the `ChangeDisplaySettingsExW`
   call at `0x41364` plus the commit at `0x4137a` with their arguments and return
   codes. Verify byte guards against the loaded image first, bound the duration,
   read values only, and detach cleanly.

Items 1 and 2 are read-only and would likely resolve the question without any
instrumentation. Nothing here justifies changing a driver, a display setting or
the vendor installation, and nothing here requires a Fedora-side replay to the
iPad.
