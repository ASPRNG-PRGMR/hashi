# HASHI: next session after Fedora static inspection

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
