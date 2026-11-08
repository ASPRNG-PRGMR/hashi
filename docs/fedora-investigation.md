# Fedora investigation — 2026-11-01

**Inference:** The copied agent has a concrete path from `usbmuxd_connect` to direct Winsock I/O on its returned socket. This makes the observed Apple loopback connection a strong session-transport candidate. It does **not** establish that the historical connection carried display data. The next runtime test is in [the Fedora handoff](fedora-next-steps.md).

## Provenance and preservation — FED-E001

**Fact:** The existing Git workspace is `/home/noobiegg/Documents/github-stuff/hashi`, at commit `24857f1` when inspected. Initially only `hashi-stuff/` was untracked; tracked files were clean. No remote was created or changed. The transfer contains `hashi-main/` and `HASHI-private/` as an **already extracted tree**.

**Fact:** No HASHI transfer archive was located in the transfer or searched home-directory archive filenames. `/home/noobiegg/Downloads/usb-stuff.zip` was inspected by its member list and contains unrelated material. The ZIP inside `HASHI-private/rea-bootstrap` is the Windows Zig distribution, not the workspace/evidence transfer. The user was asked whether the transfer archive was removed or stored elsewhere; no answer was available when this log was written. Consequently **no original transfer-archive SHA-256 or extraction verification can be claimed**.

**Fact:** All 32,279 supplied regular files (751,064,767 bytes) were hashed. A walk rejected symlinks and nonordinary entries before copying selected directories into new staging. Run evidence, the transferred workspace and the REA package were copied; staged workspace/run file hashes were compared with the originals. The original transfer was not modified. The study DLL was not rebuilt; Windows executables were not run as Fedora tools.

Private root, abbreviated **P** below:

```text
/tmp/HASHI-private-fedora-20261101-9i_xb6aj
```

| Record | SHA-256 |
| --- | --- |
| `P/transfer-manifest.json` — original per-file hashes | `9d6d480efb71d1c06dad0d7e8c479eccff73a8d819fbb31164b05324c6ae650c` |
| `P/evidence-index.json` — Fedora Evidence IDs and output hashes | `f15b920830bf53b3376d574fbe94dddcd9718fc45eb353539e2a9d837ca33013` |

**Fact / limitation:** P is mode 0700 on `/tmp` tmpfs and is not durable across reboot. This session permits writes only in the source workspace and `/tmp`, with configuration directories protected. Original private material arrived inside the workspace; it remains there unchanged under the now-ignored `/hashi-stuff/` directory to avoid making volatile staging its only copy. All **new** raw analysis is outside the repository. Durable relocation of both sets remains necessary; `.gitignore` is not relocation. See the handoff before rebooting.

| Historical Windows path | Fedora mapping |
| --- | --- |
| `C:\Users\noobieGG\Downloads\hashi-main` | `P/staging/hashi-main` |
| `C:\Users\noobieGG\HASHI-private\runs\20261031-184820` | `P/staging/HASHI-private/runs/20261031-184820` (abbreviated **R**) |
| `C:\Users\noobieGG\HASHI-private\tools\rea-6.8.0` | `P/tools/rea-6.8.0`; JavaScript diagnostics only |
| `C:\Program Files (x86)\Splashtop\Splashtop Wired XDisplay\Agent\SWXDAgent.exe` | `R/binaries/SWXDAgent.exe` |
| Same vendor directory, `libusbmuxd.dll` | `R/binaries/libusbmuxd.dll` |
| Windows Ghidra 12.1.2 / JDK 21.0.12 installations | Not present in the transferred tree; no Fedora equivalent installed by this session |

The complete machine-readable mapping is `P/path-mapping.json`. All five required documents were read completely. The four newer Windows documents were imported unchanged into `docs/`; the existing handoff agrees with the transferred handoff identity. Corrections in `WINDOWS-CODEX-HANDOFF.md` (removed 2026-11-08) and actual later observations override the older roadmap. Windows helper scripts remain in `hashi-stuff/hashi-main/scripts/` and its staged copy.

## Verified artifact identities

**Fact:** All three measured SHA-256 values equal the supplied expected values. PE headers independently confirm the architectures and preferred image bases below. Versions in this table are attributed to the transferred Windows identity records, not a new Fedora runtime observation.

| Artifact under R | Architecture / preferred base | SHA-256 |
| --- | --- | --- |
| `study-build/ex06_hashi.dll` | x86-64 / `0x180000000` | `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786` |
| `binaries/SWXDAgent.exe` | x86 / `0x400000` | `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c` |
| `binaries/libusbmuxd.dll` | x86 / `0x10000000` | `f198c3649d934fe6dc1004541d06844348009d792ea02fbb79d706ef30fdeda3` |

**Fact (Windows records):** Agent product version `1.5.8.3`, file version `1.58.9.6924`; DLL file/product metadata `1, 0, 10, 5`. The user reported extended display working. One cable cycle removed/recreated the Apple/XDISPLAY entries and agent socket while both process IDs persisted. Apple device services were `WINUSB` and `usbccgp`, associated with driver version `538.0.0.0`; bundled `usbaapl64.sys` was not established as active. These observations have not been repeated on Fedora or in a VM.

## Tool readiness — FED-E002

| Tool | Fedora observation |
| --- | --- |
| OS / CPU | Fedora 44 Workstation, x86_64 |
| Node / npm on PATH | Node `24.20.0`, npm `12.0.2`; another Codex-managed Node is `24.19.0` |
| Default Java | OpenJDK `25.0.4.1` runtime; no `javac` on PATH |
| Reusable full JDK | Temurin `21.0.10+7-LTS`, both `java` and `javac`, `/opt/st/STM32CubeMX/jre`; STM32CubeIDE also contains this version |
| Ghidra | No installation found in the inspected tool locations or transfer |
| REA | Transferred package `6.8.0`; Linux Node can run its version and doctor commands |
| TShark | `4.6.9`; `capinfos` available; no capture acquired |
| Compilers / disassembler | GCC `16.2.1`, Clang `22.1.8`, GNU objdump `2.46.1-1.fc44`; no Zig on PATH |

**Fact:** Installed REA's `engines.node` requires `^22.23.4 || ^24.22.1 || >=26.12.1`; both discovered Nodes fail it. `doctor --provider ghidra --json` exits 1 with unsupported Node and missing Ghidra. Scoped `setup --client codex --skill=false --dry-run` exits 1, reports `needs_human`, and lists **zero planned/applied actions**. This is prerequisite validation, not an applied configuration transaction. Existing Codex configuration remains unchanged; its hash is in `P/setup/config-state.json`.

**Fact (primary documentation):** Ghidra [12.1.4 declares Java minimum/compiler 21](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.4_build/Ghidra/application.properties); [12.2 declares 25](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.2_build/Ghidra/application.properties). **Decision:** Prefer 12.1.4 with the existing full JDK 21 for this continuation, subject to checking the actual downloaded distribution and its Linux native decompiler. It is not described as the latest release. [REA installation requirements and scoped setup](https://github.com/morluto/rea/blob/main/docs/installation.md) were checked against the installed package.

**Fact / blocker:** Terminal HTTPS acquisition failed before download: `curl` exit 6, unable to resolve `nodejs.org`. Compatible Node and Ghidra were therefore not acquired. User-level Codex config is also outside this session's write roots. The current Codex tool catalog exposes **no REA tools**, and the user config contains no MCP registrations. An independent stdio schema attempt closed before initialization (`CONNECTION_CLOSED`); its cause was not established. A CLI version response is not MCP verification.

**Fact:** The transferred Windows `tools/list` schemas were inspected for `open_binary`, `binary_session`, `search_procedures`, `analyze_function`, `export_evidence_bundle`, and `close_binary`. Their provenance is explicitly retained in `P/setup/inherited-selected-tool-schemas.json`. No live Fedora schema discovery, Ghidra opening, new Ghidra pseudocode, or connected-client study check succeeded. No native analysis session was opened, so none remained to close. [Official Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) confirms the configuration and reconnect workflow; the remaining steps are in the handoff.

## Independent study check — FED-E003

**Fact:** PE exports are `hashi_add` RVA `0x1000` and `hashi_tick` RVA `0x1050`. GNU objdump instructions at preferred VAs independently reproduce the inherited locations. At `0x18000101c`, `add eax,ecx` computes the sum; the saved result is restored at `0x180001045` before return. There is an overflow-dependent helper call at `0x180001040`; that helper was not analyzed.

**Fact:** At `0x18000105a`, `hashi_tick` indirectly calls the import slot `0x1800b62f0`, identified as `KERNEL32!GetTickCount`. From the call through `ret` at `0x180001066`, no instruction changes EAX. The original and transferred C source hashes match and declare a `DWORD` return.

**Inference:** The inherited Ghidra `void` signature loses a preserved return value. Pseudocode remains interpretation. This Fedora check verifies exports/instructions, **not** a working Fedora Ghidra provider. The original Windows bundle remains `R/analysis/study-mcp-evidence.json`, SHA-256 `ad3db4603717f09be1aa72d6828c70659906b8aa8d2e5a697a323c56d44b4e67`. Its original `ev_*` IDs remain in [the Windows log](windows-investigation.md); Fedora IDs do not replace them.

## Focused transport findings

All addresses below are **static preferred-image VAs** unless explicitly marked RVA. Runtime address = observed module load base + RVA; preferred bases must not be used as live addresses without checking ASLR. Method: PE imports/exports, candidate executable-section references, and bounded objdump instruction ranges. Byte-pattern candidates were checked in instruction context; this is not an exhaustive control-flow analysis. Raw output and the helper are private (`FED-E004`–`FED-E007`).

### FED-E004 — DLL connect and transport boundaries

**Fact:** DLL exports include `usbmuxd_connect` RVA `0x2f90`, `usbmuxd_send` `0x3200`, `usbmuxd_recv_timeout` `0x3320`, and `usbmuxd_recv` `0x3420`. The helper at RVA `0x3b10` references the literal `127.0.0.1`, pushes `0x6987` (27015) at `0x10003cb5`, converts the port via imported ordinal 9, and calls Winsock ordinal 4 at `0x10003cd1`.

**Fact:** The connect export calls that helper at `0x10002fc9`, retains its result in ESI, invokes a request helper at `0x10002fed`, checks a reply, and returns ESI on its success path (`0x100030b7`). The request helper at RVA `0x1cd0` has a plist branch referencing `Connect`, `DeviceID`, and `PortNumber`; its port is passed through ordinal 9 at `0x10001d14`. An alternate branch exists; its runtime selection is unknown. These are local Apple-service request candidates, not established XDisplay application framing.

**Fact:** DLL send/receive wrappers call Winsock ordinal 19 at `0x10003266` and ordinal 16 at `0x10003363`. [Wine's primary Winsock export specification](https://github.com/wine-mirror/wine/blob/master/dlls/ws2_32/ws2_32.spec) maps 4/9/16/19/52 to connect/htons/recv/send/gethostbyname. **Limitation:** This mapping is a compatibility reference; the running Windows import targets still need confirmation. The copied DLL was not assumed identical to current upstream libusbmuxd source.

### FED-E005 — agent uses the returned socket directly

**Fact:** The agent's ordinary import table contains four libusbmuxd functions: device-list, list-free, connect, disconnect. It contains no named `usbmuxd_send`/`usbmuxd_recv` import. This does not rule out dynamic resolution or other paths.

**Fact:** In the routine starting at RVA `0x30bb0` (referencing the diagnostic label `CProbeUsbmuxd::Run`), the call at VA `0x430c9c` / RVA `0x30c9c` reaches the `usbmuxd_connect` import through thunk `0x562ff6`. Its port argument is loaded as a **16-bit field at connection-object offset +8**, at `0x430c96`; no numeric device port is established. The returned EAX is copied to EBP, then ECX, and passed to the routine at VA `0x4303f0` / RVA `0x303f0` by the call at `0x430cad`.

**Fact:** That routine moves ECX into ESI at `0x43042b`, loads the Winsock ordinal-19 import at `0x43045f`, and calls it at `0x430476` with this same socket, a four-byte buffer initialized to integer 4, and flags zero. It later calls it with a 16-byte buffer at `0x430590`. The receive helper reached at `0x43049a` uses ESI as its socket and calls ordinal 16 at `0x4112e8`. On the accepted path, the probe stores the original returned socket at connection-object offset +4 (`0x430d96`).

**Inference:** A successful libusbmuxd tunnel can be used for subsequent agent-level exchange through Winsock. Hooking only the DLL's exported send/recv wrappers would miss this direct path. **Hypothesis:** The four-byte exchange is an application probe or negotiation step; observe it after a successful connect before assigning a protocol name or meaning. Its execution in the historical display session remains unproved.

### FED-E006 — candidate ongoing I/O

**Fact:** At agent VA `0x42f702` / RVA `0x2f702`, instructions request a four-byte Winsock send. At `0x42f718` / RVA `0x2f718`, they request a variable-size send using ESI as length and EDI as buffer. Both read a socket from an object field +4. Another site at `0x42f921` / RVA `0x2f921` requests four received bytes. Adjacent send preparation shifts a size and combines a low byte, with a conditional byte-order conversion.

**Hypothesis:** These are framing/streaming candidates worth correlating with controlled image changes. The similarity of the +4 field to FED-E005 is insufficient by itself to establish identical runtime objects. No payload, codec, validated length field, frame boundary, encryption decision, or input format follows from this static slice. Partial sends/receives and TCP stream reassembly must be accounted for in runtime evidence.

## State at handoff

**Fact:** No application payload was captured, no Windows process was attached, and no Linux host/protocol implementation was started. The archive-provenance gap, compatible Node/Ghidra installation, Codex registration and actual MCP study check remain open. Static findings provide specific call sites and a controlled Windows experiment, rather than a recovered protocol. [Next-session instructions](fedora-next-steps.md) separate these setup tasks from the physical-iPad observation.

**Fact — return-transfer packaging:** At the user's subsequent request to transfer this directory back to Windows, 37 Fedora evidence/diagnostic files were bundled into the existing Git-ignored private transfer area as `hashi-stuff/FEDORA-private-20261101.zip`. Archive CRC and every member's SHA-256 were verified against the private originals. SHA-256: `900a096b2efd0b29667790bc35b28d6fce1ba9c936189b273205e45c912ba9f2`. This new transfer bundle preserves the selected outputs beyond `/tmp`; it is not the missing original inbound archive. `RETURN-TO-WINDOWS.md` defined the Windows continuation and the private evidence mapping; it was removed on 2026-11-08. The bundle and vendor artifacts are excluded from Git.
