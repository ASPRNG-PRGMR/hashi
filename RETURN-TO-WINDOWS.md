# HASHI: resume on Windows after the Fedora investigation

## Mode question narrowed on Fedora — 2026-11-07 (read this first)

**Fact (FED-MODE-E001):** The Fedora side traced the full mode-selection chain statically. The 1280×960 handed to the JPEG encoder is the LCI monitor's `rcMonitor` extent from `GetMonitorInfoW` — `[1920,0,3200,960]` gives exactly 1280×960 — so the captor reads the mode rather than requesting it. The captor's only `ChangeDisplaySettingsExW` routines, `CCaptor::CustomizeResolution` `0x32590` and `RestoreResolution` `0x32830`, both require `shared[+0x44] != 0` while the LCI rung requires `+0x44 == 0`, and `MirrorMode` was 0; they cannot have set it. The agent's own `CMultiDisplay::FindBestResolution` `0x42530` scorer, reconstructed from instructions, selects 1600×1200 rather than 1280×960 for this client. Decisively, the mode was **already** 1280×960 at `16:15:46Z`, before the `16:17:54Z`–`16:19:55Z` trace window.

**Next on Windows, cheapest first — two read-only checks may settle it without any instrumentation:** (1) enumerate *all* value names and data under `HKCU\Software\Splashtop Inc.\Splashtop Wired XDisplay` in both registry views and persist the enumeration, settling `ForceResW`/`ForceResH`; (2) record the persisted mode for the `LCI\IDDCX` device. Only if both leave it open, instrument one boundary across a genuine **detached → attached** transition — not another reconnect, which contains no decision: `FindBestResolution` entry/return, the agent's own `Find resolution: %d for (%d,%d)[%d]` log lines, and `ChangeDisplaySettingsExW` at `0x41364` with the commit at `0x4137a`. See [mode-selection chain](docs/fedora-mode-selection.md). Do not change a driver, display setting, pairing or the vendor installation. No push has been requested.

## Active Windows backend result — 2026-11-07

**Fact (WIN-BACKEND-E001–E004):** The working Windows agent PID 21016, executable SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`, ran LCI captor vtable RVA `0x1ac4b4` and ordinary JPEG encoder vtable RVA `0x1ac818`. The live base was `0x00590000`; the vtable addresses were `0x0073c4b4`/`0x0073c818`. On one normal iPad reconnect, its LCI sizing helper returned 1600×1200 for client 2048×1536, then monitor refresh replaced output dimensions with 1280×960 before JPEG initialization. The selected current Windows LuminonCore mode was also 1280×960; the exact driver/Windows mode-choice cause remains unknown. The user confirmed the extended display works, and the bounded trace detached cleanly. See [Fedora startup validation](docs/fedora-startup-validation.md) for evidence IDs, exact times, registry sources/defaults, failed first hook, full system-inclusive module inventory, hashes and limits.

**Fact:** The first Frida attempt failed at instruction RVA `0x31a26`; its partial raw output is preserved. The successful initialization trace and private 98-file hash index are at `C:\Users\noobieGG\HASHI-private\runs\backend-20261106`; index SHA-256 `f9fcdb8493d4dd8c30c6827b660ab7cf01d87e5d9171ef6cd1f4e5b29fd8981b`. `InitCaptor` failed-initialize fallback is StVD constructor RVA `0x37f10`, correcting the earlier OSBase statement. No protocol replay, driver/display/pairing/vendor change, or study repetition occurred. Do not run the old cable and REA plans below. No push has been requested.

## Active Fedora continuation — 2026-11-06

**Fact:** The Fedora checkout was clean on `main` at `12d6499` when this continuation began. FED-BACKEND-E001 in [Fedora startup validation](docs/fedora-startup-validation.md) maps the complete five-rung `InitCaptor` priority ladder and seven capture/thread class vtables for the unchanged agent SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`. The ladder's small integers are exception cleanup states, not persistent backend IDs. Its config source and precise availability tests are still under investigation.

**Fact:** FED-FRAME-E001 measures the 1,903 retained frames and adds a tested narrow framing parser. The user declined active Fedora replay to the iPad. No new Windows run, protocol traffic, driver changes or vendor execution occurred. Keep the next Windows observation passive. Its required full module list must include system DLLs; historical filtered `modules.json` snapshots cannot identify the capture backend. Do not run the older broad cable or REA-study plans below.

## Active Fedora continuation — 2026-11-05

**Fact:** The verified Windows investigation import is committed as `c63c354`. Read [Fedora startup validation](docs/fedora-startup-validation.md) for the current result, durable mapping, hashes and focused startup analysis. The complete original bundle and all four Windows runs are preserved at `/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z/bundle`; receipts and new analysis are in its parent directory. All 1,993 files and 191 indexed evidence records verified. Historical paths below remain provenance.

**Fact:** Fedora independently reproduced exact stream parsing of 1,903 JPEG records and twelve full image/pixel checks. Startup fields use mixed representations; client dimensions are stored after four-pixel alignment, while the later field containing 5 is written directly little-endian. That constant's meaning remains open. Subsequent static analysis distinguishes client dimensions from current monitor/encoder dimensions and traces ordinary JPEG, differential JPEG and SRx264 selection. No guessed messages were implemented.

**Fact:** The actual Codex REA 6.8.0 MCP connection now passes the Ghidra 12.1.4 study check using the unchanged, hash-verified DLL. Both exports were analyzed, evidence exported privately, and sessions closed. The incorrect recovered `void` tick signature was checked against its preserved EAX return. No rebuild or reinstallation was needed.

**Fact / inference:** The LCI sizing helper returns an initial 1600×1200 request for 2048×1536, then monitor refresh overwrites encoder dimensions before initialization. The captured Windows display and JPEGs are 1280×960. This explains why client dimensions need not equal JPEG dimensions; the exact runtime captor and driver/Windows mode decision remain unobserved. The captured capability body does not establish successful `diff_jpeg` negotiation. See FED-SIZE-E001–E003 in the Fedora report for the field trace and the precise passive Windows follow-up, if needed. No new cable cycle was performed.

New private evidence is under the preserved import's `analysis/rea-dimensions-20261105T140157Z`. All 1,993 original bundle files and 512 directories reverified unchanged. The older `completion-receipt.json` applies to import cleanup, not this continuation; the new evidence directory has its own integrity and preservation receipts.

This update governs the historical Windows execution instructions below.

## Active continuation update — 2026-11-05: ready for Fedora analysis

Read [Windows startup/framing](docs/windows-startup-framing.md) completely. **Fact:** WIN-NEXT-02 captured the complete observed startup exchange and 1,903 JPEG records on the same socket returned by usbmuxd_connect. Both application streams parse exactly as tag byte + BE24 payload length + payload. Twelve decoded records match independent white/black/white screen checks. Cleanup passed and the user confirmed the display works.

The planned Windows capture is complete. The next stage is Fedora import, offline validation and narrow startup-field analysis. Raw evidence remains private at C:\Users\noobieGG\HASHI-private\runs\startup-20261105-103819, alongside earlier runs. Use FEDORA-IMPORT-PROMPT.md and the prepared hashi-stuff bundle to reconcile changes into the existing Fedora repository, verify durable evidence copies, make scoped commits, and only then remove the temporary import directory. Startup field semantics, alternate modes and a complete interoperable protocol remain unvalidated; no speculative implementation was added. The actual REA MCP check remains separate and can be completed on Fedora.

## Active continuation update — 2026-11-04

Read [Windows source correlation](docs/windows-source-correlation.md) and [Windows return investigation](docs/windows-return-investigation.md) completely. **Fact:** The November 4 test independently checked visible screen pixels and matched twelve decoded 1280×960 JPEG send buffers to white → black → white square changes. **Inference:** Together with November 3's usbmuxd_connect socket-return proof at the matching-build direct Winsock boundary, this answers WIN-NEXT-01's focused transport/image question across two sessions. The earlier unsuccessful controls remain preserved and unexplained.

New private run: C:\Users\noobieGG\HASHI-private\runs\source-check-20261104-142811 (40 indexed records verified). All hooks detached. The next protocol investigation is WIN-NEXT-02: validate the startup exchange and stream framing; do not implement a guessed protocol. Actual REA tools are still absent from this chat despite aligned registration; a current live Ghidra study check requires Codex reconnection, not a rebuild or Fedora setup. The active workspace remains C:\Users\noobieGG\Downloads\hashi.

This update governs the older unresolved-image statements below. The new report distinguishes the earlier observed return socket from today's already-connected socket and retains that session boundary.

## Active continuation update — 2026-11-03

Read [the Windows return investigation](docs/windows-return-investigation.md) completely before executing the historical plan below. **Fact:** Active checkout is C:\Users\noobieGG\Downloads\hashi; the nested hashi-stuff\hashi-main remains historical. All 32,279 original manifest files and 30 indexed Fedora records verified. Private current run: C:\Users\noobieGG\HASHI-private\runs\return-20261103-232442.

**Fact:** WIN-NEXT-01 established that usbmuxd_connect returned the Apple-loopback socket (handle 1352, 127.0.0.1:62541 → :27015), with port argument 6789, and direct agent Winsock sends carried decodable 1280×960 JPEG buffers. **Unresolved:** The corrected controlled-square run returned six identical images, so causal image dependence is not verified. Read the DPI-placement correction and negative result; do not repeat the original test helper unchanged or claim a complete protocol.

**Fact:** All four bounded traces detached cleanly. REA/Ghidra/JDK doctor passes and registration is aligned, but no REA tools were exposed in this chat. A fresh actual Codex study check still requires reconnection. No study rebuild, Fedora setup, driver change or protocol implementation was performed. The next step is to verify the controlled test window's actual visibility/image source, then correlate decoded content; see the new report's final section.

The remainder is the preserved November 1 handoff and background; this update governs conflicting path, tool-connection and transport-unknown statements.

Prepared 2026-11-01. This file and the accompanying directory are the complete context for the next Windows Codex session. Proceed with the work, not just a plan.

## Objective and current priority

Implement a Linux host compatible with the **unmodified Splashtop Wired XDisplay iPad app over USB**. **Fact:** No Linux host implementation or validated application protocol exists yet.

**Next question:** Does the observed agent-to-Apple loopback connection carry XDisplay session data, or only control traffic? Fedora static analysis identified specific call sites for a Windows runtime experiment. Do not implement a speculative protocol.

Read these files completely, from the workspace containing this file:

1. `WINDOWS-CODEX-HANDOFF.md` — governing corrections and background.
2. `docs/windows-investigation.md`
3. `docs/windows-components.md`
4. `docs/protocol-observations.md`
5. `docs/windows-next-steps.md`
6. `docs/fedora-investigation.md` — newer static findings, hashes and limitations.
7. `docs/fedora-next-steps.md` — especially **WIN-NEXT-01** and its RVA table.

This return handoff determines the execution environment: **Windows**, not Fedora. New observations supersede older plans. Do not repeat completed Windows setup or follow Fedora prerequisite-installation instructions on Windows. Do not assume the current machine is a VM.

## Locate and preserve the transferred evidence

The outer directory/ZIP may be named `hashi-stuff`. Discover the workspace by this file and `docs/fedora-investigation.md`, rather than relying on the outer directory name. Within that workspace, expect:

```text
RETURN-TO-WINDOWS.md
WINDOWS-CODEX-HANDOFF.md
docs/
hashi-stuff/                         # private transfer material, ignored by Git
  hashi-main/                       # older Windows workspace, not the new root
    scripts/                        # original Windows observation helpers
  HASHI-private/
    runs/20261031-184820/
      binaries/SWXDAgent.exe
      binaries/libusbmuxd.dll
      study-build/ex06_hashi.dll
      analysis/                     # original Windows REA evidence
    tools/rea-6.8.0/
  FEDORA-private-20261101.zip
  FEDORA-private-20261101.zip.sha256
```

**Fact:** The nested Fedora ZIP was created for this return transfer. It is **not** the missing original Windows-to-Fedora archive. Its SHA-256 is:

```text
900a096b2efd0b29667790bc35b28d6fce1ba9c936189b273205e45c912ba9f2
```

It contains 37 files: Fedora raw analysis, setup diagnostics, original-file manifest, evidence index, verification record and historical path mapping. Every archived file was compared with its source. The binaries and original Windows evidence remain in the sibling `HASHI-private` tree; they are not duplicated in this nested ZIP.

Preserve the outer archive and record its SHA-256 if it is locally available. Verify the nested ZIP hash before extracting. Inspect member names and types, reject path traversal/absolute paths/links, and extract into a **new private directory outside the source workspace**, preferably under the existing `C:\Users\noobieGG\HASHI-private` if that path is actually present and suitable. Never overwrite the old Windows run or an existing import.

Verify `evidence-index.json` against the extracted Fedora files. Original artifact hashes are in `docs/fedora-investigation.md`; the original 32,279-file manifest covers the earlier transfer tree, before the new Fedora ZIP was added. Do not count new packaging files as missing original evidence. Its `HASHI-private/...` and `hashi-main/...` relative paths are rooted at the workspace's nested `hashi-stuff` directory.

Map historical `/tmp/HASHI-private-fedora-20261101-9i_xb6aj/analysis/...` to the extracted Fedora bundle's `analysis/...`. Map its former `staging/HASHI-private/runs/20261031-184820/...` to the transferred Windows run or a verified existing private copy. Record the new Windows paths. Linux paths inside raw output are provenance, not paths that must exist on Windows. The private PE helper also contains historical Linux paths; preserve it and adapt a separate copy only if needed.

Keep all subsequent binaries, captures, traces and decompilation outside the source repository. The ignored nested transfer directory is included only to transport existing private evidence. Do not publish this whole ZIP or force-add its contents to Git. Preserve existing workspace changes, user configuration and any existing Git remote; do not invent a remote or overwrite the user's older Windows workspace.

## Reuse the working Windows setup

REA repository: **https://github.com/morluto/rea**; npm package `rea-agents`, CLI `rea`.

**Fact (previous Windows session):** REA 6.8.0, Ghidra 12.1.2 and full JDK 21.0.12 were installed and the study DLL was successfully analyzed through Codex's actual MCP connection. Historical locations and verification Evidence IDs are in the Windows documents. Discover and reuse those installations; do not assume transferring a directory transfers an active MCP connection.

Check the current Codex MCP tools and their live schemas. Verify a small actual REA call. If registration is missing, inspect current requirements, preview a Codex-only setup transaction, preserve existing configuration and apply the authorized setup under current permissions. If reconnection is needed, document the exact step and continue independent inspection. Shell doctor or a standalone SDK connection alone is not the live Codex check.

Use the **transferred** study DLL for any necessary provider check, without rebuilding it. Verify its hash, discover its exports, obtain instructions/pseudocode for a returned function, export evidence privately and close the session. Preferred image base `0x180000000`; add/tick RVAs `0x1000`/`0x1050`. Treat the inherited `void` return inferred for `hashi_tick` as an error to check against source and instructions.

## Execute the focused investigation

**Fact (Windows observations):** Agent product version `1.5.8.3`, file version `1.58.9.6924`; agent and loaded libusbmuxd are x86. An agent connection to Apple Mobile Device Service at `127.0.0.1:27015` disappeared and returned during one cable cycle while both PIDs persisted. The user reported a working extended display. Active Apple device services were WINUSB/usbccgp, driver version 538.0.0.0; bundled usbaapl64.sys was not established as active.

**Inference from Fedora instructions:** The agent can pass the socket returned by `usbmuxd_connect` directly to Winsock send/recv. Hooking only libusbmuxd's send/recv exports can miss this path. No runtime payload or numeric device-side port has been established; 27015 is the local Apple-service endpoint.

Follow **WIN-NEXT-01** in `docs/fedora-next-steps.md`. Rediscover current PIDs, binary hashes, module load bases, available capture/debugging tools and working display state. Use the verified x86 module-relative RVAs; do not use preferred static addresses as live addresses without ASLR adjustment. Record the connect arguments/returned socket, associate it with a loopback connection, and observe direct Winsock I/O during a static test image and one controlled small-region image change. Repeat the image-change trial. Ask the user for cable/iPad actions only when needed; continue independent work while waiting.

Capture successful byte counts and return values, not just requested lengths. Keep raw payloads private and use test content. Account for TCP reassembly, partial I/O, socket reuse and trace overhead. Keep USB transfers, usbmux control, application messages and video frames distinct. If new capture-driver installation or a disruptive change is necessary, explain the concrete action and follow applicable permissions before disturbing the working setup.

Work autonomously on ordinary inspection, local setup, focused static analysis and documentation. Do not bulk-decompile the application or prioritize kernel-driver reversing. Mark every meaningful conclusion **Fact**, **Inference**, or **Hypothesis**, retaining hashes, Evidence IDs, timestamps, RVAs, supporting instructions and limitations. Update the Windows investigation/protocol notes and next-session handoff with what actually ran, what remains unknown and the next discriminating observation. Do not claim Fedora or a VM reproduced Windows runtime behavior.
