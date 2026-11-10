# Windows investigation log

## Startup-capture update — 2026-11-05

Read [Windows startup/framing](windows-startup-framing.md). The planned WIN-NEXT-02 capture is complete, including same-connection startup/image proof, full successful byte streams, observed framing validation and clean detach. Fedora can now continue offline. Preserve all historical evidence.

## Source-correlation update — 2026-11-04

[Windows source correlation](windows-source-correlation.md) establishes the missing controlled-content result with independently checked screen pixels and twelve decoded JPEG send buffers. The transport conclusion combines today's fresh-process content evidence with the prior matching-build usbmux return trace; no same-connection continuity across sessions is implied. All hooks detached and 40 new evidence records verified.

## Return update — 2026-11-03

See [Windows return investigation](windows-return-investigation.md) for the current path mapping, complete integrity verification, actual tool availability, runtime socket proof, JPEG sample checks, DPI-control failure and next discriminating observation. **Fact:** usbmuxd_connect returned the observed Apple socket and direct Winsock sends carried valid JPEG image buffers. **Unresolved:** Controlled square-to-payload correspondence. Historical completion statements below apply to the earlier setup task only.

The complete Windows investigation handoff was read and adopted as the investigation plan. Its SHA-256 at intake was `8EE60814530901F724B2B848F3804FB2692D7B04D9240B99C40762922BDBE434`. Its corrections supersede older project notes. The workspace at the time was an extracted copy with no `.git` repository; no remote was created or assumed.

## Environment and evidence locations

**Fact, observed 2026-10-31:** Windows 11 Home Single Language, x64, build 26300 (`10.0.26300`), PowerShell 7.6.5; computer manufacturer/model HP OMEN Gaming Laptop 16-ap0xxx. `HypervisorPresent=True` was reported. **Inference:** The manufacturer/model identifies an HP laptop environment; the hypervisor flag alone does not identify a guest VM or prove USB redirection. C:, D:, E: were fixed NTFS volumes.

Private evidence root: `<private-evidence-root>/runs/20261031-184820`, outside this checkout. Raw diagnostics, study build products, INF copies, endpoint observations and analysis output stay there. Ordinary reviewed notes and reproduction scripts stay in this workspace. No vendor binary was copied into the source workspace, and no USB payload, pairing record, screenshot or memory dump was acquired.

Windows CIM queries initially failed in the restricted shell with access denied. Read-only queries succeeded through the session's reviewed out-of-sandbox execution. Protected service/WUDF process module enumeration still did not return modules; this is missing evidence, not proof that a DLL is absent.

## Analysis toolchain

**Fact:** Static analysis used Ghidra 12.1.2 with a full JDK 21.0.12; the native
x64 decompiler check passed. A portable Zig 0.17.0 provided a C compiler for the
study builds below, downloaded from the official release index with its archive
SHA-256 verified and no system PATH changes. Every tool was installed outside
this checkout, under the private evidence root. Frida's optional npm install
script was blocked; no live instrumentation capability is claimed or needed for
this static check.

## Study verification

The requested pre-existing Windows study binaries were absent; the user confirmed “not there.” The workspace contained the original study C sources. No native Windows C compiler was found on PATH or in the inspected standard locations; STM32CubeIDE's discovered compiler targeted ARM embedded systems. Portable Zig was used to build two existing sources without editing them. These are **new builds**, not the historical MinGW artifacts.

Reproduce with `scripts/Build-WindowsStudy.ps1`, supplying the Zig path above and a private output directory. Both builds target `x86_64-windows-gnu`, `-O0 -g`; the DLL adds `-shared`. Exact source hashes, flags, tool version and output identities are in `study-build/build-manifest.json`.

| Artifact | Architecture / preferred image base | SHA-256 |
| --- | --- | --- |
| `study-build/ex06_hashi.dll` | x64 / `0x180000000` | `6CCAB14EA52E7B5F9D858BC98BE43A946CA48F68083A1F54A76C0D0524546786` |
| `study-build/ex01_basics.win-O0.exe` | x64 / `0x140000000` | `2D2C9CCDA10C4B3DB048FF4E13296013FF0895B3B1E518D73D81C42AFC66E817` |

**Fact:** Running the source-reviewed basics exercise with input 7 printed `small` and exited 19; input 9 printed `big` and exited 21, matching `add3(x,3,4)` and the source branch. Results: `study-build/smoke-results.json`.

**Fact:** The first Ghidra import was the study DLL, analysed headlessly from a private path. It completed on October 31 at approximately 18:59:29 +05:30. Evidence `ev_34aa1e7261a1585b5d08ba6e4cead5ab4ec4734e40ed79d3c26670ad84fad32b`, retained in `analysis/study-cli-inspect.json`, reports x64 native shared-library analysis with Ghidra 12.1.2, base `0x180000000`, 998 inventoried procedures and 171 defined strings. Counts describe Ghidra's recovered inventory, not complete source discovery. The relatively large count includes linked runtime code. A PDB reference exists, but its load state was reported unknown; complete source types are not assumed.

### WIN-SETUP-001: function-level analysis verification

**Question:** Can the analysis toolchain obtain meaningful Ghidra instructions and pseudocode from the study binary?

**Classification: Fact.** On November 1, live `open_binary` selected the same SHA-256-verified DLL with `provider_id: ghidra`. `search_procedures` with literal pattern `hashi_` returned exported names `hashi_add` at `0x180001000` and `hashi_tick` at `0x180001050` (Evidence `ev_30654f07f2a4c8860c28438c9d4aba6b979a5e7087c1b60d46f12f40736a926f`). Both were then analyzed by their returned addresses with `detail: complete`.

- **Fact:** `hashi_add` spans `0x180001000`–`0x18000104d` inclusive, RVA `0x1000` relative to preferred base `0x180000000`. Instructions receive operands in ECX/EDX, execute `ADD EAX, ECX` at `0x18000101c`, and return the saved result in EAX. The function also tests signed overflow and conditionally calls `0x180001b80`. Its source is `return a + b;`. **Inference:** The extra overflow branch is compiler-added checking in this build; the helper's complete semantics were not analyzed. Ghidra guessed unsigned parameter types although the source declares `int`. Evidence: `ev_562b64be379e522aab324eb1cc4294c898717962c80c7e10d3f63aa694e4ef88`.
- **Fact:** `hashi_tick` spans `0x180001050`–`0x180001066`, RVA `0x1050`. Its indirect call at `0x18000105a` uses IAT location `0x1800b62f0`, resolved by Ghidra to `KERNEL32.DLL::GetTickCount`. No subsequent instruction overwrites EAX before return. The source explicitly returns `DWORD` from `GetTickCount`, but Ghidra rendered this wrapper as `void`/undefined. **Inference:** That decompiler return type is inaccurate for the supplied source/binary; its imported call and instructions remain useful evidence. Evidence: `ev_e8372ae6c123bc700197a3f97c18356febbf4bba862fd17849ca43147e8d60f1`.

These are static preferred-image addresses, not ASLR-adjusted runtime addresses. Ghidra's import log included warnings in linked runtime code; no completeness or correctness claim is made for all 998 functions. The targeted instruction checks, recovered exports, source comparison, and separate executable smoke results establish this limited setup verification. The DLL was statically analyzed, not loaded/executed as part of the Ghidra check.

All three evidence records were exported to private `analysis/study-analysis-evidence.json` (53,982 bytes; SHA-256 `AD3DB4603717F09BE1AA72D6828C70659906B8AA8D2E5A697A323C56D44B4E67`), then the analysis session was closed cleanly. Overview and function-level analysis are verified; annotation persistence, runtime instrumentation and USB capture are not verified by these checks.

## Windows observations

See `windows-components.md` for binary identities and driver associations and `protocol-observations.md` for the action timeline and evidence hashes. The October 31 initial state lacked an agent and present Apple device. The user then opened the app and connected the iPad, reporting a working extended desktop. Follow-up unplug/replug snapshots kept the same agent process and showed its Apple-service socket disappear and reappear with a new local port. No wire framing, codec or iPad application port has been recovered.

The earlier process collector's broad `*Splashtop*` path filter also matched the Ghidra installation during analysis. Those rows do not belong to XDisplay. The script was narrowed to the installed vendor directory for future runs; original snapshots were preserved. The monitor script's original change display could also report TCP row-order changes; interpretation compares semantic endpoint sets, not raw JSON ordering. Each sample takes query time plus a two-second delay; timestamps, not an assumed exact sampling rate, bound transitions.

No Wireshark/TShark, USBPcap, Process Monitor or Process Explorer was found by the initial PATH, uninstall-record and standard-directory checks. This is a bounded search, not a whole-disk absence claim. No capture driver was installed and no display or pairing configuration was changed.

**Fact:** On November 1, private copies of `SWXDAgent.exe` and `libusbmuxd.dll` were retained under `binaries/`. Source hashes before/after copying and destination hashes all matched the October 31 inventory. `binary-copy-manifest.json` retains paths, observation times and SHA-256. No vendor function decompilation was performed in this setup session.

## Completion boundary

The requested environment inspection, component inventory, analysis-toolchain setup and small study verification are complete. One controlled disconnect/reconnect cycle is evidenced and reproducible using the saved scripts; repeatability over multiple cycles remains untested. No protocol recovery or Linux implementation is claimed.
