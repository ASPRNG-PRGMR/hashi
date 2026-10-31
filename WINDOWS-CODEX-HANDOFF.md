# HASHI: standalone handoff for Codex on Windows

Prepared on **2026-10-31**. Read this entire file before starting. It is intended to be the **only project context supplied to a new Codex session on Windows**. No earlier conversation, repository checkout, study exercises, captures, or installed analysis tools should be assumed available.

## 1. Your assignment

Help investigate **Splashtop Wired XDisplay's Windows host** so that HASHI can eventually implement a compatible Linux host for the **unmodified Splashtop iPad app over USB**. Start with the existing Windows installation, establish an observable baseline, set up REA where appropriate, and investigate the host agent and its communication with the iPad.

The user reports that **iTunes and Splashtop XDisplay are already installed and running on Windows**. They intend to use Codex on that machine. This does not establish that the iPad is currently connected, that mirror or extended mode currently works, or that development tools are installed. Verify those points.

Proceed with ordinary inspection, documentation, and reversible work within the user's requested scope. Discover information locally before asking the user for it. Keep making independent progress when a physical action or installation prompt requires the user. Follow the current session's permissions; this document does not grant administrator rights or override approval requirements. Explain a necessary approval in terms of the concrete action and its effect. Do not ask permission repeatedly for work already authorized.

**First milestone:** a working analysis setup or a precise setup diagnosis, an inventory of the actual XDisplay components, identification of the likely communication process, and one reproducible connect/disconnect observation with evidence. Full protocol recovery is a later milestone; do not promise it from one capture.

## 2. Project identity and intended result

**HASHI** means **Host Adapter for Splashtop Hardware Interop**; 橋 means “bridge.”

The eventual result is a Linux machine presenting itself as a compatible wired-display host to the existing iPad application. Mirroring, a separate extended desktop, and later input handling are the intended capabilities.

The original development workspace is:

```text
/home/noobiegg/Documents/github-stuff/hashi
```

That is a path on the user's Fedora machine, not a Windows path or a remotely accessible resource. No HASHI GitHub remote URL is supplied here. **Do not invent one or assume the repository is publicly available.**

At handoff, HASHI is a research project with documentation and small C learning exercises. There is **no Linux host implementation yet**. Several notes and exercises are uncommitted or untracked, so a future clone alone may omit current work. You can begin using only this file; missing original documents are not a blocker.

The planned Linux implementation uses Rust, `usbmuxd`/`libimobiledevice`, an appropriate virtual-output backend, and an encoder such as FFmpeg or GStreamer once the accepted codec and framing are established. These are design candidates, not implemented or proven choices. `evdi` was the leading virtual-display candidate; compositor integration remains unresolved. Treat DRM writeback as a possible capture mechanism, not as proof that an independent virtual display can be created.

The current working model is:

```text
Windows desktop / display system
    -> IddCx virtual-display driver in extended mode
    -> frame handoff / IPC / encoding boundary (ownership still to discover)
    -> XDisplay host agent and/or its helper modules
    -> Apple device communication stack / USB multiplexed transport
    -> unmodified iPad application

Future Linux equivalent:
Linux display/capture source -> HASHI protocol and encoding pipeline
    -> usbmuxd/libimobiledevice transport -> unmodified iPad application
```

The location of encoding, exact IPC, transport endpoints, and application protocol are **unknown**. Mirror mode may obtain frames differently from extended mode.

## 3. Evidence inherited from the earlier investigation

These are records from the previous environment, mainly consolidated on **2026-10-14**. They are not fresh observations of the Windows machine you are using now. Reconfirm paths, versions, architecture, and behavior before relying on them.

| Prior observation or conclusion | Status and qualification |
| --- | --- |
| Apple Mobile Device Service and Bonjour were present after installing the Apple stack. | Recorded observation. Determine the actual processes, drivers, and endpoints used in a session; installed components alone do not prove every component is involved. |
| Mirror mode worked in the earlier installation; extended mode required an additional display-driver installation. | Historical observation; reproduce separately on this machine. |
| A LuminonCore Display package contained `lci_iddcx.inf`, `lci_iddcx.dll`, and its catalog. | Recorded package inspection; previous driver version was `1.0.2018.1204`. |
| The INF contained `UmdfLibraryVersion = 2.15`, `UmdfExtensions = IddCx0102`, `AddService = WUDFRd`, and `UpperFilters = IndirectKmd`. | Recorded INF evidence supporting a UMDF/IddCx display driver and the Microsoft kernel plumbing. |
| The UMDF DLL was installed at `C:\Windows\System32\drivers\UMDF\lci_iddcx.dll`. | Historical path; inspect the active package and loaded module to confirm. |
| `lci_proxywddm.sys` existed at `C:\Windows\System32\drivers\lci_proxywddm.sys`, described as “LuminonCore WDDM PROXY.” | Recorded kernel-driver inventory. Its exact responsibility remains unknown. |
| Driver packages were published as `oem1.inf` and `oem2.inf`. | Historical names only. Windows assigns these per installation; never hard-code them as identities. |
| `SWXDAgent.exe` may be the host agent. | Unverified name reported in earlier third-party research. Discover the actual executable/process; do not assume this name or path. |
| The host agent/application transport deserves priority over exhaustive driver reversing. | Research priority based on the interoperability objective and separate mirror/extended behavior. Discover whether helper processes or DLLs own parts of the transport. |
| The display driver is probably a console IDD. | Inference, not confirmed binary evidence. |
| The 2018 version/date suggests an older IddCx build target. | Inference only; timestamps and version strings do not establish the exact API level. |

The previous study plan covered x64 calling conventions, PE files, pointers/structures, callbacks, MSVC idioms, WDF/IddCx tables, and a Microsoft sample driver. You do not need to complete a four-week course before collecting basic observations. Explain the relevant concepts as the investigation encounters them.

### Corrections that must survive this handoff

- **`IddCx0102` is not proof of IddCx API version 1.2.** It is a class-extension binding identifier. Keep the driver's build/minimum target separate from the OS's available framework version. [`IddCxGetVersion`](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/iddcx/nf-iddcx-iddcxgetversion) reports the current IddCx version; that result alone does not recover every build-time choice.
- **`AppleSSD.sys` is not evidence of iPad USB transport.** It was an irrelevant storage-driver entry in the earlier notes. Find the actual Apple mobile-device USB driver; `USBAAPL64.sys` is a historical candidate, not a mandatory current filename.
- **An unmatched function is not automatically proprietary transport code.** Compiler differences, CRT/library code, optimizations, and different framework versions also defeat binary matching. A match is not proof of shared source either.
- The Microsoft public IDD sample was recorded as post-dating the 2018 vendor driver. Use it to understand framework patterns; do not assume the vendor copied that sample.
- Failure to find a named pipe or shared-memory handle does not prove ALPC. Record the gap and design another observation. Do not declare kernel debugging necessary without evidence.
- Swapchain assignment establishes a frame-processing path; it is not a callback that must fire once per frame. Frame acquisition happens in the processing loop.
- USB transfer boundaries, usbmux framing, application-message boundaries, and video-frame boundaries are distinct. Do not equate them without evidence.
- Ports, connection direction, compression, encryption, video codec, packet fields, and input-message formats are unknown until observed. An import or a suggestive string is a candidate, not proof of runtime use.

## 4. Research rules and reporting

Use these labels for every meaningful conclusion:

- **Fact:** directly observed evidence or a clearly attributed statement from primary documentation. Distinguish “documentation says” from “observed in this installation.”
- **Inference:** a conclusion supported by facts but not directly established.
- **Hypothesis:** a proposed explanation with a concrete way to test it.

For binary claims, retain the artifact SHA-256, file/product version, architecture, provider/version, function address or RVA, and relevant instruction/call evidence. Distinguish static virtual addresses/RVAs from ASLR-adjusted runtime addresses. For capture claims, retain capture hash, frame numbers, timestamps, filters, direction, and the action being performed.

Ghidra pseudocode and agent-generated names are interpretations. Compare important conclusions with instructions and runtime observations. Do not turn a guessed type, an unresolved indirect call, or an absent symbol into a fact.

The project's existing scope is independent interoperability research: describe behavior and implement independently. Do not copy vendor code into HASHI or publish vendor binaries/decompiled source. This is **not a formal two-team clean-room arrangement**, and this document makes no legal determination.

Keep raw USB captures, pairing material, memory dumps, ETL/PML logs, desktop frame dumps, vendor binaries, and decompilation output outside any publishable repository. Publish only reviewed behavioral notes and independently written code. Use a simple test pattern or blank test desktop for captures. Do not copy device pairing records or unrelated personal content into chat or reports. REA runs analysis locally, but tool results provided to Codex enter the model context; local execution is not a promise that all derived information stays on the machine. [REA overview and data handling](https://github.com/morluto/rea).

## 5. Tools, official sources, and Windows limitations

### REA

**Canonical repository: [https://github.com/morluto/rea](https://github.com/morluto/rea).**

REA means “Reverse Engineer Anything.” It exposes analysis workflows through a CLI and MCP server so an agent can request structured findings from tools such as Ghidra. The npm package is **`rea-agents`** and its CLI is **`rea`**. Do not confuse it with HASHI, a Rust dependency, or a complete XDisplay protocol implementation.

- [Official website](https://rea.tools/)
- [npm package](https://www.npmjs.com/package/rea-agents)
- [Releases](https://github.com/morluto/rea/releases)
- [Installation and setup](https://github.com/morluto/rea/blob/main/docs/installation.md)
- [Windows Ghidra support](https://github.com/morluto/rea/blob/main/docs/windows-ghidra-p0.md)
- [Client configuration and troubleshooting](https://github.com/morluto/rea/blob/main/docs/client-configuration.md)
- [CLI reference](https://github.com/morluto/rea/blob/main/docs/cli.md)
- [Native investigation workflows](https://github.com/morluto/rea/blob/main/docs/native-investigation.md)
- [MCP contracts](https://github.com/morluto/rea/blob/main/docs/mcp-contracts.md)
- [Detailed packet inspection](https://github.com/morluto/rea/blob/main/docs/packet-captures.md)
- [Packet summary workflows](https://github.com/morluto/rea/blob/main/docs/pcap-analysis.md)

At handoff, GitHub's latest release was **6.8.0**. Repository `main` can describe features beyond a published package. Recheck the selected release's requirements and the running server's actual tools; do not infer installed capability from a web page alone.

The documented Windows Ghidra path is **experimental**, on **Windows x64**, and provides read-only inspection of admitted native PE applications/DLLs. It requires an existing Ghidra installation and full JDK. It does not provide Ghidra GUI control, persistent annotation editing, automatic live-process tracing, or general kernel-driver support. Do not assume `lci_proxywddm.sys` is admitted simply because a driver uses PE format. Targets and temporary storage must satisfy the provider's local NTFS/path checks; UNC paths and reparse points are restricted. [Windows scope](https://github.com/morluto/rea/blob/main/docs/windows-ghidra-p0.md).

REA's detailed `inspect_packet_capture` integration currently runs on Linux with TShark and `prlimit`; it rejects Windows. Its current limits include 32 MiB input and bounded execution/output. USB decoding depends on the installed dissectors, and upstream's fixtures do not establish USB/PCAPNG coverage. Capture on Windows and inspect with Windows Wireshark/TShark directly, or transfer a copy to Fedora for a separately verified REA workflow. Keep original captures intact when creating analysis subsets. [Packet inspector boundaries](https://github.com/morluto/rea/blob/main/docs/packet-captures.md).

### Codex and supporting tools

| Tool | Purpose and primary source |
| --- | --- |
| Codex on Windows | Use the desktop app's Windows-native agent environment for this investigation. The terminal setting and agent environment are separate. Current documentation calls the desktop surface the ChatGPT desktop app: [Windows guide](https://learn.chatgpt.com/docs/windows/windows-app). |
| Local MCP support | The desktop app, CLI, and IDE share MCP configuration on the same Codex host. [MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). |
| Node.js + npm | Runtime/package manager for REA. [Official downloads](https://nodejs.org/en/download). |
| Ghidra | Native static analysis. [Official releases](https://github.com/NationalSecurityAgency/ghidra/releases). |
| Full JDK | Java runtime and compiler for Ghidra. [Microsoft Build of OpenJDK](https://learn.microsoft.com/en-us/java/openjdk/download). |
| Process Explorer | Find actual processes, loaded DLLs, and open handles. [Microsoft Sysinternals](https://learn.microsoft.com/en-us/sysinternals/downloads/process-explorer). |
| Process Monitor | Observe filtered filesystem/registry/process activity and useful call stacks. It is not a universal API-call or payload recorder. [Microsoft Sysinternals](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon). |
| Wireshark / TShark | Capture inspection and field extraction. [Official downloads](https://www.wireshark.org/download.html), [TShark manual](https://www.wireshark.org/docs/man-pages/tshark.html). |
| USBPcap | Windows USB transfer capture. [Wireshark USB setup](https://wiki.wireshark.org/CaptureSetup/USB), [USBPcap project](https://desowin.org/usbpcap/). |
| Microsoft IDD sample | Optional framework reference. [Sample directory](https://github.com/microsoft/Windows-driver-samples/tree/main/video/IndirectDisplay). |

Check Windows-version requirements before choosing downloads. No purchased decompiler is needed for the proposed Ghidra workflow. Visual Studio/WDK installation is optional later work, not a prerequisite for identifying the running host or capturing traffic.

## 6. Establish a local workspace and environment

If this file is in an existing HASHI workspace, inspect that workspace and preserve its changes. Otherwise create a local working directory such as `%USERPROFILE%\hashi` and a separate private evidence directory under `%LOCALAPPDATA%\HASHI`. Do not require the user to transfer the original repository before starting. Do not create/push a remote repository as part of this setup.

Example directory initialization; adapt to verified existing locations:

```powershell
$hashiRoot = Join-Path $env:USERPROFILE 'hashi'
$hashiPrivate = Join-Path $env:LOCALAPPDATA 'HASHI'
$hashiRun = Join-Path $hashiPrivate ('runs\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))

New-Item -ItemType Directory -Force -Path $hashiRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $hashiRoot 'docs') | Out-Null
New-Item -ItemType Directory -Force -Path $hashiRun | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $hashiRun 'binaries') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $hashiRun 'captures') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $hashiRun 'analysis') | Out-Null
```

Verify these are ordinary local NTFS paths before using the Windows REA provider. Avoid cloud placeholders, VM shared folders, network shares, and redirected paths for its targets/runtime. Keep ordinary notes in the workspace and private raw evidence in the separate directory. Record chosen locations in a local manifest; do not overwrite earlier runs.

Collect a short inventory, without dumping unrelated environment variables or credentials:

```powershell
Get-CimInstance Win32_OperatingSystem |
    Select-Object Caption, Version, BuildNumber, OSArchitecture
$PSVersionTable.PSVersion
Get-Command node, npm.cmd, java, javac, rea.cmd, git, tshark, capinfos -ErrorAction SilentlyContinue |
    Select-Object Name, Source
Get-Volume -ErrorAction SilentlyContinue |
    Select-Object DriveLetter, FileSystem, DriveType, SizeRemaining
```

Run `node --version`, `npm.cmd --version`, `java -version`, and `javac -version` for commands that exist. Record whether Windows is physical or a VM and how the iPad is attached when that is discoverable. The earlier project used a GNOME Boxes `win11` VM on Fedora; **do not assume this is still the machine in use**. A Windows-only session must not claim access to Fedora's services or files.

The earlier Linux shell had Node 24.20.0, a Java 25 runtime, TShark, and no discovered Ghidra or `javac` on PATH. Those observations say nothing about this Windows environment.

## 7. Install and verify REA with Ghidra

### 7.1 Choose a compatible toolchain

As documented at handoff, REA requires Node **22.x >= 22.23.4**, **24.x >= 24.22.1**, or **26.12.1+**. Verify the package's current `engines` declaration before installing or upgrading. [Package manifest](https://github.com/morluto/rea/blob/main/package.json).

REA accepts Ghidra **12.x >= 12.1**; its Windows guide records verification with **12.1.4**. Ghidra 12.2 is now also released, so 12.1.4 must not be described as the latest. Respect the chosen distribution's `application.java.min`/`application.java.max`: 12.1 releases require JDK 21+, while 12.2 requires JDK 25+. Use a **full Windows x64 JDK**, including `javac`, and the distribution's matching native decompiler. REA does not install these prerequisites. [Ghidra setup](https://github.com/morluto/rea/blob/main/docs/installation.md#ghidra), [Ghidra releases](https://github.com/NationalSecurityAgency/ghidra/releases).

Reuse compatible tools already installed. Acquire missing tools from the official links above within the current session's installation authorization. Preserve the working Apple/XDisplay installation while setting up analysis tools.

### 7.2 Acquire REA and configure the provider

Use an ordinary PowerShell terminal and a trusted tools/bootstrap directory outside the target application and HASHI source tree. The paths below are examples and **must be replaced with discovered paths**. Avoid changing the system-wide execution policy just to invoke an npm PowerShell shim; `npm.cmd` and `rea.cmd` can be used instead.

```powershell
$hashiBootstrap = Join-Path $hashiPrivate 'rea-bootstrap'
New-Item -ItemType Directory -Force -Path $hashiBootstrap | Out-Null
Set-Location $hashiBootstrap

npm.cmd view rea-agents dist-tags.latest
npm.cmd view rea-agents@6.8.0 engines --json
```

Select and record a release after checking its requirements. The following uses the **6.8.0 handoff snapshot**, not an assertion that it will remain the latest:

```powershell
npm.cmd install --global rea-agents@6.8.0

# Replace these example paths with the real installed directories.
$env:GHIDRA_INSTALL_DIR = 'C:\tools\ghidra_12.1.4_PUBLIC'
$env:JAVA_HOME = 'C:\tools\jdk-21'
$env:REA_ANALYSIS_PROVIDER = 'ghidra'

rea.cmd --version
rea.cmd doctor --provider ghidra --json
rea.cmd providers --json
```

Record the installed REA version, actual Node/Java/Ghidra paths and versions, and diagnostic results. If a compatible REA is already installed, inspect it before changing it. If using a later release, substitute the explicit selected version and retain that fact in the manifest.

### 7.3 Connect it to Codex

From the same terminal with the provider variables set:

```powershell
rea.cmd setup --client codex --dry-run
rea.cmd setup --client codex
```

Review/apply the setup transaction under the session's applicable permissions. It registers the server and matching workflow instructions; REA preserves selected provider paths. Restart/reconnect Codex afterward. Inspect the active server list and call a small REA tool to establish that the client actually exposes it. Shell-only `doctor` success is insufficient. [REA setup](https://github.com/morluto/rea/blob/main/docs/installation.md), [client diagnostics](https://github.com/morluto/rea/blob/main/docs/client-configuration.md).

Codex's default configuration location is `~/.codex/config.toml` for the active host; respect an existing `CODEX_HOME` override without repurposing it. The desktop app also exposes **Settings -> MCP servers**. Preserve other registrations/settings. A PowerShell environment variable alone does not configure an already running desktop app; inspect the registered server environment. [Official MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

If REA's tools appear, inspect their advertised schemas before calling them. Typical native workflows use `open_binary`, inventory/search tools, and `analyze_function`; tool names and available arguments can change. Do not invent parameters or claim a tool ran when it was unavailable.

If a restart is required, write a short resumption note with completed steps and the exact next check. Continue independent inventory work where possible. Do not spend the whole investigation repeatedly reinstalling a provider: capture the specific failure and use Ghidra directly or ordinary Windows tools while it is unresolved.

### 7.4 Perform a small, meaningful verification

Use a locally built tiny C fixture if a compiler is already installed, or a small identified native Windows executable/DLL. Confirm its architecture and hash first. The original HASHI exercises are optional and are **not included** in this handoff.

```powershell
# Example: set this to the selected local test artifact.
$hashiTarget = 'C:\path\to\small-native-test.exe'
Get-FileHash -LiteralPath $hashiTarget -Algorithm SHA256
rea.cmd inspect $hashiTarget --provider ghidra --json
```

Select a real function returned by the inventory and obtain its instructions/pseudocode. Repeat this through Codex's actual MCP connection. Verify the function address and output make sense, retain diagnostics, and close the session using the advertised interface. Inspection success alone does not verify every REA capability. [Native workflow](https://github.com/morluto/rea/blob/main/docs/native-investigation.md).

## 8. Identify the real Windows components

Start with a narrow process/service search. This is discovery, not a claim that every matching process belongs to XDisplay:

```powershell
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -match 'Splashtop|SWXD|WUDFHost|AppleMobileDevice|mDNSResponder' } |
    Select-Object Name, ProcessId, ParentProcessId, ExecutablePath

Get-CimInstance Win32_Service |
    Where-Object { $_.Name -match 'Apple|Bonjour|Splashtop|Luminon' -or
                   $_.DisplayName -match 'Apple|Bonjour|Splashtop|Luminon' } |
    Select-Object Name, DisplayName, State, ProcessId, PathName

pnputil.exe /enum-drivers
```

Save relevant outputs privately and summarize only the relevant entries. Access-denied/null fields are missing evidence, not proof that no process or module exists. Expand the search using installation/uninstall records and the process tree when the initial name filter misses the target. Avoid a recursive whole-drive binary search as the first step.

For each actual candidate:

1. Record executable path, PID and observation time, parent process, user/session context, architecture, and file/product version. PIDs are temporary.
2. Use Process Explorer's DLL and handle views to identify loaded vendor/Apple modules and candidate named objects. Locate the particular `WUDFHost.exe` instance containing `lci_iddcx.dll`; do not attribute all UMDF hosts to XDisplay.
3. Identify the active LuminonCore driver packages and read their INF files. Use actual current `oem*.inf` associations, original names, provider/version, service definitions, and device interfaces.
4. Copy only selected binaries needed for static analysis into the private evidence directory. Hash original and copy and record the source path/time. Do not patch or replace the installed files. If a file changes while being copied, resolve its identity before analyzing it.
5. Record relevant open local/network endpoints and module relationships. A socket alone does not establish the iPad protocol, and USB traffic need not appear on a normal network interface.

The initial component manifest should distinguish the desktop UI, host/service process, transport/codec helpers, UMDF display driver, kernel helper, and Apple services. Leave unknown relationships unknown.

## 9. Capture controlled behavior before broad decompilation

### 9.1 Establish the baseline

Record XDisplay host version, iPad app version if available, Windows build, iPad/iOS version if available, connection method, and display topology. Avoid retaining unnecessary device identifiers. Verify what is working before installing a capture driver or changing configuration.

Use separate short experiments:

| Experiment | One controlled action | Main question |
| --- | --- | --- |
| A | Observe with iPad disconnected. | Which processes/services are always present? |
| B | Connect an already trusted iPad and start the app. | Which process and endpoint participate in session establishment? |
| C | Hold a simple static image in mirror mode. | What traffic/control activity persists at idle? |
| D | Change only the test image or animate a small region. | Which traffic changes correlate with image updates? |
| E | Switch to extended mode if already supported. | Which display/driver/IPC activity changes? |
| F | Disconnect and reconnect. | What closes, resets, and repeats? |

Coordinate physical cable/UI actions with the user as needed. Timestamp each action, capture start/stop, mode, resolution, and observed result. Repeat a key observation before promoting an inference to a fact. Do not erase pairing or reset a working configuration merely to simulate first-time pairing; an ordinary reconnect is already a useful initial experiment.

### 9.2 Process and IPC observations

Use Process Monitor with filters derived from the actual process IDs/names and relevant paths. Compare before/during/after connection. Look for named pipes, device opens, file mappings or named section/event handles, and plausible driver interfaces. Process Explorer's handle view complements Procmon; neither tool alone establishes every IPC payload or API sequence. [Process Monitor](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon), [Process Explorer](https://learn.microsoft.com/en-us/sysinternals/downloads/process-explorer).

If evidence points to a specific boundary, plan a focused API/debugger observation of that boundary. Candidate API families include file/pipe I/O, shared sections/events, `DeviceIoControl`, socket I/O, RPC/COM, and Apple device APIs actually present in the imported/loaded modules. Record buffer lengths and call context before trying to interpret payloads. Treat debugger attachment as a separate experiment that can affect timing and process stability.

### 9.3 USB acquisition and inspection

Windows can acquire USB transfers using USBPcap with Wireshark. Software USB capture records host-stack transfer requests/completions rather than every electrical bus transaction. Follow the installed tool's instructions, identify the iPad's USB device/bus, and check that the selected capture actually contains its traffic. [Wireshark USB setup](https://wiki.wireshark.org/CaptureSetup/USB).

If USBPcap needs installation, explain the specific driver installation/restart requirements before disrupting a working display session. Use the actual installation privileges available. If Windows is a VM with USB redirection, record where capture occurs; the Fedora host's usbmon path is an alternative only when that host is accessible and correctly sees the redirected device's traffic.

Keep initial captures short. Confirm payloads are not truncated by the capture length setting. Preserve the original file and hash, then work on copies. For each run, note device/bus selection, direction, transfer type, timestamps, drop/error indicators, and relevant frame numbers. Do not hard-code TShark field names from memory: enumerate installed fields with `tshark -G fields` and query a narrow subset.

Analyze in layers:

1. Separate relevant USB transfers from unrelated devices and duplicated request/completion representations.
2. Identify/reassemble the relevant higher-level transport streams where supported.
3. Separate Apple pairing/device setup and transport framing from XDisplay's application handshake.
4. Test candidate message boundaries, lengths, byte order, message types, sequencing, and session transitions against repeated observations.
5. Correlate changes with static-image, image-update, mode-switch, and disconnect actions.
6. Investigate codec/container markers only in the correctly reconstructed payload stream.

A large payload does not prove it is a video frame. High entropy does not prove encryption. An unavailable dissector does not prove the protocol is absent. If encryption is established, record what the capture still reveals and investigate the relevant plaintext boundary inside the host process; do not claim ciphertext alone exposes the application protocol.

## 10. Use REA to answer focused binary questions

Prioritize the identified host agent and its relevant loaded DLLs. Begin with imports, strings, exports, and a small candidate list, then follow references into particular functions. Favor a persistent MCP analysis session for related questions; cold imports can be expensive. Export useful evidence before closing, and keep durable notes outside the session. The Windows provider cannot be assumed to save annotations. [REA native guide](https://github.com/morluto/rea/blob/main/docs/native-investigation.md), [CLI reference](https://github.com/morluto/rea/blob/main/docs/cli.md).

Useful questions to pursue:

- Which functions reference observed endpoint names, service identifiers, error messages, or handshake constants?
- Which callers reach transport read/write operations, including dynamically resolved imports?
- Which functions build or parse candidate length/type headers?
- How are buffers queued between frame acquisition, encoding, and transport?
- Which state changes occur around connection, stream start, resolution negotiation, and teardown?
- What remains unresolved because of function pointers, missing types, or stripped symbols?

For each answer, return a small evidence-backed finding and its next validation step. Do not bulk-decompile the entire application as the first action or write vendor pseudocode into the source repository. Do not assume a function name guessed by the agent existed in the original binary.

When the driver becomes relevant, use the framework model: IddCx provides desktop surfaces to a UMDF driver. Locate the `IDD_CX_CLIENT_CONFIG` callback registration and WDF/IddCx function-table uses. The assign/unassign swapchain callbacks and the frame-acquisition loop are useful candidates for tracing frame ownership and handoff. Resolve table offsets against matching headers/types rather than guessing names from offsets. [Microsoft IDD overview](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/indirect-display-driver-model-overview).

## 11. Optional deeper display-driver work

Do this when it answers a specific unresolved question; it must not postpone basic host/USB observations.

### IddCx traces and frame capture

Microsoft documents WPP tracing and registry-controlled frame capture. For modern Windows builds, per-frame WPP logging can use flags `0x1f4`; flag interpretation is build-dependent, and decoding requires matching symbol information. Registry controls live under `HKLM\System\CurrentControlSet\Control\GraphicsDrivers`. Consult the exact instructions for the installed build before applying changes. [Microsoft debugging guide](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/indirect-display-debugging).

Treat this as a controlled optional experiment: record existing settings, retain a restoration plan, capture a bounded test, stop the trace, and restore changed settings. Do not disable watchdogs or enable debugger-break flags as a routine setup step. A kernel debugger is not automatically required to collect an ETL trace.

Frame dumps help establish observed image content/dimensions and correlate activity. A PNG dump alone does not prove the original GPU surface format, the wire codec, or normal frame cadence. Trace overhead can affect timing. Keep frames and ETLs private and use test content.

### Microsoft sample and binary comparisons

If needed, obtain [Microsoft's IndirectDisplay sample](https://github.com/microsoft/Windows-driver-samples/tree/main/video/IndirectDisplay). Consult [Microsoft's current WDK installation guidance](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk) for supported Visual Studio/SDK/WDK combinations instead of inheriting old version claims.

Build an x64 **Release + matching PDB** pair for optimized-code comparison and **Debug + matching PDB** for learning. Keep build configurations and pairs separate. A PDB provides symbols/types; Release builds can have PDBs too. Inspect the sample without replacing/installing it over the working vendor display driver.

Prefer Ghidra's built-in Version Tracking and, where useful, BSim. Earlier notes found BinExport/Ghidra compatibility problems and treated Diaphora as IDA-only; recheck those projects before investing in optional integrations. Do not make third-party diff tooling a prerequisite for protocol research. Candidate matches need review, and unmatched code is not automatically vendor-specific functionality.

## 12. Deliverables and evidence templates

Create these progressively under the chosen workspace, adapting names if equivalent files already exist:

```text
docs/windows-investigation.md   - current state and chronological experiment log
docs/windows-components.md      - verified component/relationship inventory
docs/protocol-observations.md   - behavioral findings and unresolved hypotheses
docs/windows-next-steps.md      - concise next-session handoff
```

Private run manifests, tool diagnostics, copied binaries, captures, and other raw artifacts belong under the private evidence root. Preserve previous runs. Do not mark a missing task complete just because tooling was installed.

Use this finding template:

```text
Finding ID:
Question:
Classification: Fact / Inference / Hypothesis
Claim:
Environment and relevant software versions:
Artifact/capture identity: filename + SHA-256
Location: function RVA/address, packet/frame number, or trace event
Method: tool/version + exact relevant query/filter
Observation:
Interpretation:
Alternative explanations / limitations:
Next validation:
```

Use this experiment template:

```text
Experiment ID and timestamp/timezone:
Purpose and single changed variable:
Starting state: device connected/trusted, app state, display mode/resolution
Capture/trace setup and private output locations:
Action timeline:
Observed outcome:
Relevant evidence references:
Repeatability:
Cleanup/restoration completed:
What remains unknown:
```

For each tentative protocol message, record direction, connection/channel, state, candidate header fields/offsets/endianness, length semantics, payload observations, and supporting examples. Unknown values stay unknown. Redact identifiers/secrets in publishable examples and preserve references to private originals so analysis remains auditable.

At the end of a work session, state exactly what was observed, what was inferred, what failed, and the next concrete experiment. Record REA configuration/provider problems separately from target-analysis problems. Leave enough information to resume without this conversation or an agent's remembered context.

## 13. Recommended execution order and completion criteria

1. **Inspect the environment and working XDisplay setup.** Identify missing tools and current session constraints; establish workspace/private evidence locations.
2. **Inventory the actual processes, packages, and binaries.** Do not wait for REA to gather this evidence.
3. **Configure REA/Ghidra and verify one small real analysis through Codex.** If blocked, preserve the diagnosis and continue with available tools.
4. **Record one short connect/disconnect experiment.** Correlate process/module/endpoint observations and, when available, USB capture.
5. **Investigate a small number of host-agent functions suggested by those observations.** Record addresses and explicit uncertainties.
6. **Repeat with controlled image changes and then extended mode.** Use deeper driver analysis only where it resolves a gap.
7. **Produce a behavioral protocol description and a next-session handoff.** Do not begin a speculative full Linux host based only on guessed framing.

The first milestone is complete when the current component inventory and baseline experiment are reproducible, the REA integration has either been exercised or its exact blocker documented, and the next protocol question has a specific test. Later milestones are a validated application handshake, acceptance of a synthetic test frame/stream by the real iPad app, then a Linux prototype and real display pipeline. Evidence from the real unmodified app determines interoperability success.

**Begin now with environment inspection and component discovery.** If only this Markdown file exists, create the workspace and notes described here and proceed. Ask for user input only when local discovery cannot supply required information or when a concrete physical/privileged action needs their participation.
