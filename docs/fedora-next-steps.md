# HASHI: next session after Fedora static inspection

## Steady state decoded — FED-STREAM-E001, 2026-11-08

**Fact:** `CConnectBase::Run` (RVA `0x2f580`) and `CConnectBase::ReceiveThread` (RVA ~`0x2f8c0`) are decoded and implemented in `hashi_stream.py`. **The whole host→device direction is now reproducible offline byte-for-byte:** re-encoding all 1,903 captured image records and prepending the rebuilt handshake yields the entire 130,375,177-byte outgoing application stream, rebuilt and captured SHA-256 both `85b81dd7e307b371e45be5dda6eb26bfc35c3fe789af1c32ec2a70413a2cb123`. The same header codec appears in three independent places now, so it is *the* framing rule. Pacing is `1000 / fps` measured from `GetSystemTime`'s `wMilliseconds` alone, so the agent's own elapsed calculation wraps every second.

**Fact:** The inbound TLV channel is the **input** channel — handler `0x440110` builds a 28-byte Win32 `INPUT` and calls `SendInput`. Its 17-entry dispatch table is mapped. `CConnectBase::SendReconfigVideo` is decoded: field 0 = 1 carrying the output dimensions from shared `+0x1c`/`+0x20`, swapped when `+0x24` is set — the same field 0 the startup HELLO uses, so resize is decoded rather than guessed.

**Limitation that governs the next step:** the captured incoming stream is 346 bytes — 294 usbmux, 52 startup, **zero** steady state. No inbound record and no reconfiguration was ever observed. The input dispatch and the reconfig encoder therefore have no byte-exact validation.

**Next, offline:** the individual input paths behind the 17-entry table (to map `field0` to event kinds and settle absolute vs normalised coordinates), the `0x70` subtype branch, `CConnectBase::HandleEvent`, the trailing "extra data" block and the capability/`diff_jpeg` parser. **Next, needing the iPad connected:** observing actual inbound records, which requires someone touching the iPad screen while a capture runs. See [steady state](fedora-steady-state.md).

## Startup handshake decoded — FED-START-E001, 2026-11-07

**Fact:** The whole observed startup exchange is one 0x792-byte function at RVA `0x303f0`, named `CProbeUsbmuxd::DoHandshake` by the agent's own strings. It is now decoded and implemented in `hashi_startup.py`, validated offline with no device and no Windows: the rebuilt host sequence reproduces the captured outgoing startup bytes **byte-for-byte**, the captured incoming stream parses with zero remainder, all 1,903 image headers re-encode exactly, and the full 130,375,177-byte application stream is accounted for. Three previously open items are closed: the 2048×1536 fields are the client dimensions (aligned `((v-1) & ~3) + 4`), the little-endian `05 00 00 00` is field 1 of the `0xfc` record written with no `htonl`, and the 4-plus-12 receive split is by design. Shared `+0x40` is identified as the byte-order-mode flag. See [startup handshake](fedora-startup-handshake.md).

**Next, still all on Fedora:** The remaining protocol unknowns are the trailing "extra data" block's content and the capability/`diff_jpeg` parser; the receive helper `0x112e8` and the ongoing send path `0x2f6c5`–`0x2f718` for the steady-state image loop; and, for completeness of FED-MODE-E001, `AttachExtendDisplay`'s callers and the unclassified `ChangeDisplaySettingsExW` sites. The JPEG side is already bounded: all 1,903 frames share one DQT/DHT table set and 4:2:0 sampling, so a host can emit the same tables without guessing. **The meaning of the `0xfc` record's literal 5 is still a Hypothesis — do not promote it.** The legacy native-order fallback (type 1) is decoded but unobserved. Nothing here authorises transmitting these bytes to the iPad; that remains the user's decision.

## Mode-selection chain resolved — FED-MODE-E001, 2026-11-07

**Fact:** The open sizing question from WIN-BACKEND-E003/E004 is now answered structurally. The dimensions the encoder receives are the selected monitor's `rcMonitor` extent from `GetMonitorInfoW`; `[1920,0,3200,960]` yields exactly the observed 1280×960. The captor's only mode-setting routines are gated off in any LCI configuration, the agent's own best-mode scorer selects 1600×1200 rather than 1280×960 for this client, and the 1280×960 mode already existed before the traced window opened. Full addresses, the reconstructed score formula, the remaining unknowns and the exact later-test evidence are in [mode-selection chain](fedora-mode-selection.md); the established rules are implemented in `hashi_mode.py` with tests beside the reused framing parser.

**Fact (user-reported, 2026-11-07):** The 1280×960 mode was the user's own selection in Windows display settings — the size they want for the iPad — and Windows persisted it for `LCI\IDDCX`. The sizing question is fully closed: mechanism established statically, cause supplied by the user. The two read-only Windows checks previously proposed here are withdrawn, and no Windows access is needed for it.

**Next, all on Fedora:** Decode the startup state machine at RVA `0x303f0` — one 0x792-byte function that contains every observed host→iPad send (`0x30476`, `0x30592`, `0x306e7`, `0x30837`) and the reply handling, with receive helper `0x112e8`. The agent is the host, so this is the host-side protocol logic, and decoding it turns the observed byte sequence into established field semantics and validation rules. Then build a byte-exact offline harness that re-serialises the captured outgoing stream and diffs it against the capture, which validates a host implementation without sending anything to the iPad. Afterwards: `AttachExtendDisplay`'s callers, the unclassified `ChangeDisplaySettingsExW` sites, and the capability/`diff_jpeg` parser. Alternate captors, differential JPEG and a full interoperable host remain open. Do not implement guessed messages and do not replay Fedora startup to the iPad.

## Fedora import of the backend transfer — 2026-11-07

**Fact:** The Windows backend transfer was received and verified on Fedora. See
[Fedora backend import](fedora-backend-import.md) for the archive hash, the
139-member pre-extraction safety audit, the 138 verified payloads, the verified
98-file private index, the two documentation-only bundle commits and the
fast-forward integration to `4193abc`. The private evidence root for this
transfer is recorded there; it stays out of Git. No push was performed.

## Windows backend observation complete — 2026-11-07

**Fact (WIN-BACKEND-E001–E004):** On the working Windows installation, the loaded LCI captor vtable was RVA `0x1ac4b4`, and the ordinary JPEG encoder vtable was RVA `0x1ac818`. A single normal cable reconnect with the bounded passive observer captured 2048×1536 client values, a 1600×1200 LCI sizing-helper result, then 1280×960 after monitor refresh and at ordinary JPEG initialization. The post-reconnect LuminonCore current mode and rectangle were 1280×960. Read the new top section of [Fedora startup validation](fedora-startup-validation.md) for timestamps, addresses, hashes, registry defaults, probe cleanup and limitations. The user confirmed the display works. A first broader hook failed at RVA `0x31a26`; its raw output is retained, while the successful narrowed run detached cleanly.

**Next:** The active captor and JPEG class are established for this session. The remaining sizing question is why Windows/the LCI driver selected 1280×960 despite the helper's 1600×1200 request; available modes include both. A future experiment should instrument only the specific mode request/return boundary after static caller analysis, retaining current mode and monitor identity. It requires fresh justification, not another transport/framing or study check. Alternate captors, differential JPEG negotiation, the field 5 and a full interoperable host remain open. Do not implement guessed messages or replay Fedora startup to the iPad.

## Current continuation — 2026-11-06

**Fact:** See FED-BACKEND-E001 and FED-FRAME-E001 in [Fedora startup validation](fedora-startup-validation.md). The five-rung `InitCaptor` ladder and seven capture/thread vtables were independently mapped from the unchanged agent. The small integers in the ladder are exception cleanup states, not captor IDs. The config source and full availability semantics remain open. The existing Windows module snapshots filter system paths and cannot identify the capture backend.

**Fact:** The repository now contains only the validated record boundary and JPEG SOI/EOI/SOF0 inspection with synthetic tests. The 1,903 observed frames have one DQT/DHT table variant and 4:2:0 sampling. These facts do not settle which JPEG encoder class ran. The user declined active Fedora replay to the iPad; keep the Windows plan passive.

**Next:** Trace the config fields back to their exact source and finish the availability helpers. Decode the listed hook conventions and produce a reviewed probe specification before probe code. Inspect the existing Windows runner and agent before extending them. Complete phase-separated frame analysis and verify a full module inventory requirement. Only then request the narrow Windows session for runtime values, modes, monitor and DPI context. Do not repeat framing or REA study checks.

## Current continuation — 2026-11-05

Start with [Fedora startup validation](fedora-startup-validation.md). **Fact:** Windows WIN-NEXT-01/02 are complete for the recorded configuration; Fedora reproduced the exact tag/BE24 parsing, 1,903 JPEG headers and twelve decoded pattern checks. The complete verified private bundle is under `/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z/bundle`, with fresh evidence and receipts in its parent. The older volatile paths and setup blockers below are historical.

**Fact:** Installed Linux Node 24.22.1 / Ghidra 12.1.4 / REA 6.8.0 under `~/HASHI-private/tools/fedora-20261105`, reusing `/opt/st/STM32CubeMX/jre` (full JDK 21.0.10). Scoped doctor and Codex registration checks pass; actual REA tools are still absent in this running agent. Reconnect the Fedora Codex client and execute the unchanged-study check below using the durable DLL path. Do not rebuild the study or repeat prerequisite installation.

**Next investigation:** Follow connection-object fields `+0x14`, `+0x18`, `+0x40`, `+0x68` from startup into capture/resize/encoder selection. Explain the 2048×1536 client values versus 1280×960 JPEG content. The later startup field 5 is written little-endian; its semantic meaning remains unproved. The captured zero-prefixed later response does not establish successful `diff_jpeg` capability parsing. Keep alternate modes unobserved and do not implement guessed messages. No Windows reconnect experiment is needed merely to finish the transfer.

Updated 2026-11-01. **Objective:** implement a Linux USB host compatible with the **unmodified Splashtop Wired XDisplay iPad app**. **Fact:** No Linux host exists here yet; the application protocol is not established. Do not implement a guessed protocol from strings, four-byte sends, or codec-library filenames.

**Return-transfer update:** For the next session on Windows, start with [RETURN-TO-WINDOWS.md](../RETURN-TO-WINDOWS.md). The new private Fedora outputs have also been preserved in the Git-ignored `hashi-stuff/FEDORA-private-20261101.zip`, verified against their originals. Include the ignored transfer folder when making the private ZIP; `git archive` omits it. The Windows return handoff records the bundle hash and extraction/path mapping. The `/tmp` limitation below describes the original analysis location, which is no longer the only copy of the bundled outputs.

Read [Fedora investigation](fedora-investigation.md), [Windows handoff](../WINDOWS-CODEX-HANDOFF.md), [Windows investigation](windows-investigation.md), [components](windows-components.md), [protocol observations](protocol-observations.md), and [Windows next steps](windows-next-steps.md). The handoff's corrections and later observed evidence govern older README/study-roadmap claims. Label meaningful conclusions **Fact**, **Inference**, or **Hypothesis**.

## Preserve evidence first

**Fact:** Existing workspace: `/home/noobiegg/Documents/github-stuff/hashi`, original inspected commit `24857f1`. It was preserved. No Git remote was invented. Four Windows documents were imported unchanged; current notes and a README pointer were added. The original transfer is ignored by Git at `hashi-stuff/` and still contains private material. Never stage it with `git add -f`.

Current private analysis root (**P**):

```text
/tmp/HASHI-private-fedora-20261101-9i_xb6aj
```

**Fact / unresolved:** This is volatile tmpfs. New evidence needs a durable private location before reboot. The original transfer archive was not located; `hashi-stuff` was already extracted. A filename/member-list search and the archive-location question are documented in the log. Do not substitute the unrelated Downloads `usb-stuff.zip` or Windows Zig ZIP as the transfer archive. If the original becomes available: preserve it, record its SHA-256, reject absolute/traversing/link/special-file members and unreasonable expanded sizes, extract to a new staging directory, then compare its files with `P/transfer-manifest.json` without overwriting either source.

This session's write policy allowed only the repository and `/tmp`; user-level config and durable directories outside the repository were unavailable for writing. In a normal host terminal or a session granted the required directory access, create a **new** destination and copy both the original transfer and the new analysis. For example, after verifying the source still exists:

```bash
hashi_saved="$HOME/HASHI-private/fedora-20261101"
# mkdir without -p for the final component deliberately refuses an existing run.
mkdir -p "$HOME/HASHI-private"
mkdir -m 700 "$hashi_saved"
cp -a /tmp/HASHI-private-fedora-20261101-9i_xb6aj "$hashi_saved/analysis-run"
cp -a /home/noobiegg/Documents/github-stuff/hashi/hashi-stuff "$hashi_saved/original-transfer"
```

Verify every copied original against `analysis-run/transfer-manifest.json`, and each new evidence file against `analysis-run/evidence-index.json`, before considering any cleanup of the original in-repository transfer. Update this handoff and the path mapping with the durable location. The copy commands do not delete anything. Manifest/index hashes are in the investigation log. If `/tmp` has disappeared, the original input remains in `hashi-stuff`, but new raw Fedora outputs will need regeneration.

Historical Windows run `C:\Users\noobieGG\HASHI-private\runs\20261031-184820` maps to `P/staging/HASHI-private/runs/20261031-184820` (**R**). Windows workspace maps to `P/staging/hashi-main`. Vendor binaries are in `R/binaries`; transferred study DLL in `R/study-build`. Preserve `P/path-mapping.json` and original hashes. Never assume a staged path containing an old preferred address is a runtime address.

## Finish Fedora REA setup

Canonical REA repository: **https://github.com/morluto/rea**; npm package **`rea-agents`**, CLI **`rea`**. See [official setup](https://github.com/morluto/rea/blob/main/docs/installation.md) and [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

**Fact:** The current client is Codex. No REA tools are connected in this session. REA 6.8.0 JavaScript diagnostics run, but its doctor rejects Node 24.20.0; the other discovered Node is 24.19.0. Setup dry-run produced zero actions. Ghidra was not found. Terminal download access failed DNS. A standalone MCP schema attempt also closed before initialization; it was not a successful client check. No user configuration was changed.

1. Restore permitted terminal download access, or supply official Linux distributions locally. Install a supported **Linux** Node (e.g. 24.22.1; verify `engines` again) in a durable tools directory. Reuse npm if compatible. Do not run the transferred Windows Zig or Windows native REA module as Linux tools.
2. Obtain a [Ghidra 12.1.4 distribution from the official release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build). It permits reuse of the full Temurin JDK 21.0.10 at `/opt/st/STM32CubeMX/jre`. Check `java`, `javac`, downloaded `Ghidra/application.properties`, and the Linux x86-64 native decompiler. Choosing Ghidra 12.2 instead requires a full JDK 25; the default Java 25 runtime alone is insufficient.
3. Install the pinned `rea-agents@6.8.0` package for Linux into a durable private tools prefix, recording package/archive hashes and exact versions. Reusing its transferred JavaScript was useful for diagnostics, but does not validate a Windows-built dependency tree as a complete Linux installation. Do not install optional analysis engines for this task.
4. Set actual absolute `GHIDRA_INSTALL_DIR`, `JAVA_HOME=/opt/st/STM32CubeMX/jre`, and `REA_ANALYSIS_PROVIDER=ghidra`. Run `rea doctor --provider ghidra --json`; preserve the output privately. All selected prerequisites must pass.
5. With the correct Linux Node on PATH, run `rea setup --client codex --skill=false --dry-run`. Review the exact command, arguments, environment and destination (`/home/noobiegg/.codex/config.toml` unless an existing genuine override applies). Preserve the current config and unrelated registrations. Apply the authorized scoped transaction with `rea setup --client codex --skill=false --yes` when filesystem policy permits it. Do not repurpose HOME/CODEX_HOME to pretend registration succeeded.
6. **Exact reconnection step:** after successful setup, restart/reconnect the Codex client using this Fedora host, inspect its MCP server/tool list, and call its actual REA `binary_session` tool according to the live schema. Save that result. A new terminal, CLI doctor, or standalone SDK helper does not establish this connection. If no REA tools appear, report that separately and continue independent static work.

The source session already authorizes ordinary setup; the unresolved issues are prerequisites and filesystem capability, not a need to ask the user to approve the same task again.

## Required live study check

Use `R/study-build/ex06_hashi.dll`, SHA-256 `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. **Do not rebuild it.** It was built on Windows from the original C sources with Zig 0.17.0 because the historical binaries were missing.

Inspect **live advertised schemas first**. The inherited 6.8.0 contracts provide this sequence as a reference, not a claim that the tools are currently available:

1. `open_binary` with absolute `path` and `provider_id: "ghidra"`.
2. `search_procedures` with `pattern: "hashi_"`, `mode: "literal"`, `detail: "complete"`; inspect returned functions/exports before choosing a procedure.
3. `analyze_function` with a returned `procedure` and `detail: "complete"`; obtain instructions and pseudocode for `hashi_add` and `hashi_tick`.
4. `export_evidence_bundle` with a **new absolute private** `path`, preserving Evidence IDs; inspect export success and hash the file.
5. `close_binary` according to its schema, including on failures after a successful open.

**Fact:** Fedora objdump already independently verified preferred base `0x180000000`, add RVA `0x1000`, tick RVA `0x1050`, and the GetTickCount IAT at `0x1800b62f0`. The tick call at RVA `0x105a` leaves EAX intact through return at `0x1066`. Source says `DWORD`; inherited Ghidra said `void`. Do not accept that signature or the inferred add signedness without instruction/source review. New Fedora Ghidra analysis remains uncompleted, distinct from the successful Windows MCP check.

## Focused static continuation

Use only the matching copied x86 binaries. Agent SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`; DLL `f198c3649d934fe6dc1004541d06844348009d792ea02fbb79d706ef30fdeda3`. Static preferred bases are `0x400000` and `0x10000000`, respectively. Product/file versions are `1.5.8.3` / `1.58.9.6924` for the agent.

**Inference:** The loopback socket is a strong session-transport candidate because DLL connect returns its Apple-service socket and the agent passes it to direct Winsock I/O. This is stronger than a suggestive string but still lacks runtime confirmation. See FED-E004/005 in the log and private hashed instructions.

| Candidate | Module-relative RVA | Purpose / limitation |
| --- | --- | --- |
| Agent probe routine | `0x30bb0` | Device enumeration and connect; diagnostic label `CProbeUsbmuxd::Run` is present. |
| Agent call / return around `usbmuxd_connect` | `0x30c9c` / `0x30ca1` | Capture actual device handle, 16-bit port and returned socket. Numeric app port remains unknown. |
| Agent subsequent check routine | `0x303f0` | Receives returned socket in ECX; starts direct I/O. |
| Agent first direct send / following send | `0x30476` / `0x30590` | Requests 4 and 16 bytes; purpose/execution must be observed. |
| Agent receive helper call site | `0x112e8` | Direct Winsock receive on ESI. |
| Agent candidate ongoing sends | `0x2f702` / `0x2f718` | Four-byte then variable-length buffers; runtime object/socket identity unresolved. |
| Agent candidate ongoing receive | `0x2f921` | Four-byte receive request; not proof of message boundaries. |
| DLL connect export / socket connect | `0x2f90` / `0x3cd1` | Connect request and loopback Winsock boundary; port 27015 is local, not the device port. |

Open the study first when Ghidra is ready, then inspect these few routines and relevant references. Avoid broad application decompilation and kernel-driver work. Dynamic imports and indirect callers mean the static candidate inventory is not exhaustive. Keep raw disassembly/pseudocode outside the source repository.

## WIN-NEXT-01: distinguish control from session data

**Required environment:** the actual working Windows XDisplay installation and the physical iPad running the unmodified app. Fedora static analysis cannot supply this observation. Do not assume a VM reproduces it. Windows setup already succeeded; retain its existing REA/Ghidra/JDK and active WINUSB/usbccgp stack. Rediscover current PIDs, module hashes/load bases and sockets; historical PIDs 20696/8920 and source ports are not constants.

**Hypothesis:** The socket returned by the agent's `usbmuxd_connect` call is the observed Apple connection and subsequently carries image-dependent session data, in addition to setup/control exchange.

1. Re-establish the working extended-display baseline. Use the transferred `Get-WindowsBaseline.ps1` and `Watch-XDisplayConnection.ps1` from the Windows workspace's `scripts` directory. Record app/iPadOS versions if discoverable, display topology/resolution, and timestamps. Keep test content simple and record user visual confirmation separately from machine observations.
2. Start a bounded loopback capture **before reconnect**, if a suitable Windows capture interface is available. Discover interfaces rather than assuming an index. Capture filter `tcp port 27015` targets the known local boundary; retain all agent connections to that endpoint and correlate process socket snapshots. Do not install a capture driver or disrupt the working configuration silently. A focused x86 debugger/API trace is an alternative if capture is unavailable.
3. At agent RVA `0x30c9c`, record the two stack arguments (device handle and port; preserve both raw bytes and numeric interpretation). At `0x30ca1`, record EAX. Use actual module bases and verify loaded IAT targets; x86 argument locations differ from x64. Associate this socket with its local/remote tuple. Record success/failure and socket lifetime so handle reuse cannot confuse separate connections.
4. Observe the **agent's direct Winsock send/recv**, not only the DLL wrapper exports. For the matched socket, record time, thread/call site, requested length, returned length/error and a bounded buffer prefix. For receive, inspect bytes **after successful return**; for send retain only the accepted positive-length prefix. Thread-aware entry/return pairing is needed. Use the candidate RVAs above to keep the trace narrow.
5. Once extended display works, run 10 seconds of a static test image, one timestamped change in a fixed small region, then another 10 seconds static. Repeat the image-change trial. Keep resolution, app/mode and cursor behavior fixed; avoid unrelated desktop traffic. Record the reconnect separately from this one-variable image test. A short tracing/capture window of roughly 60 seconds is sufficient for the first attempt; stop early if stability is affected.
6. Hash and preserve original capture/trace plus action log privately. Match the socket and connection establishment, separate the local usbmux connect exchange from subsequent stream bytes, then compare accepted bytes/rates and call sites across static/update intervals. Reassemble TCP as a byte stream; sends, segments, USB transfers, app messages and video frames are different boundaries. Do not interpret encryption, codec or complete framing from size/entropy alone.
7. Stop capture/detach and confirm the display still works. Preserve failures and timing perturbations. Compare device/socket snapshots as semantic sets, not row order; their sequential queries are intervals, not atomic events.

**Decision criteria:** Observing the same returned socket carrying post-connect buffers through the direct send path confirms that path's runtime use. Repeatable image-correlated traffic supports a display-session role, but could include control responses and does not alone identify video encoding. If only short setup/control traffic appears, search the same agent's other current sockets/module boundaries before concluding all display data bypasses Apple. Lack of captured bytes can also reflect wrong interface, missed startup, truncation or incomplete hooks.

**Still unknown:** numeric device-side port in the working session, actual application handshake, validated framing/byte order, codec, compression/encryption, resolution negotiation and input events. The exact next physical observation is: **reconnect the iPad on Windows, identify the returned socket, and observe its I/O while changing one test-image region**. No further Linux protocol implementation should precede that evidence.
