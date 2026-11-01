# Windows next-session handoff

Updated 2026-11-01. Continue in `C:\Users\noobieGG\Downloads\hashi-main`; read `WINDOWS-CODEX-HANDOFF.md` as the governing plan. This directory is an extracted workspace, not a Git checkout. Preserve existing work; no remote is known.

## Established state

- **Fact:** REA 6.8.0 is installed at `C:\Users\noobieGG\HASHI-private\tools\rea-6.8.0` and registered with Codex. Ghidra 12.1.2 and full JDK 21.0.12 are reused. The live chat exposed REA tools on November 1; `binary_session` identified an aligned `codex-mcp-client` connection. Do not reinstall or repeat setup unless a specific diagnostic warrants it.
- **Fact:** The historical Windows study executables were missing, confirmed by the user. Existing study sources were built locally using portable Zig 0.17.0. The first Ghidra target was `study-build/ex06_hashi.dll`; CLI overview and actual Codex MCP analyses of `hashi_add` (RVA `0x1000`) and `hashi_tick` (RVA `0x1050`) succeeded. Private `analysis/study-mcp-evidence.json` retains all three records; the session was closed successfully. Ghidra inferred some incorrect types, documented against instructions/source in `windows-investigation.md`. No setup or reconnect blocker remains.
- **Fact:** Installed XDisplay agent `SWXDAgent.exe` is x86, product 1.5.8.3/file 1.58.9.6924. Its connected process loaded `libusbmuxd.dll` and connected to Apple Mobile Device Service on loopback 27015.
- **Fact:** During one October 31 cable disconnect/reconnect cycle, agent PID 20696 and Apple-service PID 8920 persisted. The agent socket and Apple/XDISPLAY present-device entries disappeared, then returned with a new local port, 55435 → 60785. PIDs and ephemeral ports are historical observations, not constants for future runs.
- **Fact (user report):** A working extended desktop was visible before unplugging. The user then confirmed connection in response to the request to report its return. Mirror mode was not tested in this run.
- **Fact:** The active Apple USB device associates with `oem4.inf`, version 538.0.0.0, services WINUSB and usbccgp. Bundled `usbaapl64.sys` is not established as the active stack. LuminonCore packages were rediscovered as `oem1.inf`/`oem2.inf`, version 1.0.2018.1204.
- **Unknown:** The particular WUDF host loading `lci_iddcx.dll`; normal module queries were unavailable. Resolution properties persisted after monitor removal, so they cannot alone prove an active display.

Private run root: `C:\Users\noobieGG\HASHI-private\runs\20261031-184820`. Start with `docs/windows-components.md`, `docs/protocol-observations.md` and `docs/windows-investigation.md`; these link to raw evidence. Do not put raw captures, vendor binaries or decompilation into this source workspace.

## Next concrete protocol question

**Hypothesis:** The observed agent↔Apple connection carries XDisplay session data, rather than only device/session control. The existing lifecycle evidence does not decide this.

1. Re-establish current PIDs, device state and user-visible mode; previous snapshots are historical. Repeat the cable cycle once using a new private evidence filename to check repeatability. Use `scripts/Get-WindowsBaseline.ps1` and `scripts/Watch-XDisplayConnection.ps1`; compare semantic socket/device sets and retain query intervals.
2. Use the selected private `binaries/SWXDAgent.exe` and `binaries/libusbmuxd.dll` copies; `binary-copy-manifest.json` records their matching original/copy hashes. Recheck identity if inspecting a newer installed version. Use REA imports/exports and narrow references to identify the socket-read/write and device-connect boundaries. Use returned function addresses/RVAs; do not start with whole-program decompilation or kernel-driver analysis.
3. Record a short static-test-image interval followed by one image change. Inspect a bounded loopback capture or focused API observation of the confirmed boundary; correlate timing and byte counts before proposing application framing. Runtime attachment is a separate experiment that may affect timing.
4. For USB acquisition, first verify/install suitable Windows capture tools and identify the actual Apple bus/device. Explain any capture-driver/restart effect before disrupting the working session. No USBPcap or Wireshark installation was performed in this run. Detailed REA packet inspection is unavailable on Windows; use verified local TShark or a separately verified Linux workflow.

No iPad application port, handshake, message framing, codec, encryption, input format or Linux-compatible stream has yet been established. Keep USB transfers, usbmux messages, application messages and video frames distinct.

## Reproduce the local study check

In PowerShell, use the existing full paths; no system PATH or execution-policy change is required:

```powershell
$env:GHIDRA_INSTALL_DIR = 'C:\Users\noobieGG\Documents\Splashtop-stuff\ghidra_12.1.2_PUBLIC_20260605\ghidra_12.1.2_PUBLIC'
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-21.0.12'
$env:REA_ANALYSIS_PROVIDER = 'ghidra'
$rea = 'C:\Users\noobieGG\HASHI-private\tools\rea-6.8.0\node_modules\.bin\rea.cmd'
$study = 'C:\Users\noobieGG\HASHI-private\runs\20261031-184820\study-build\ex06_hashi.dll'
& $rea inspect $study --provider ghidra --json
```

Through live REA MCP, use `open_binary` with that path and `provider_id: ghidra`, search for `hashi_`, analyze a returned function, export evidence privately, then `close_binary`. Read the current schemas before supplying parameters. CLI success or a standalone handshake alone is not desktop MCP verification. The standalone `scripts/Test-ReaMcp.mjs` helper remains useful for diagnosing a launcher independently; it is not a substitute for the actual client check.

The initial LocalAppData install was MSIX-redirected and rejected by setup; the stable user-profile installation resolved it. Its old app-private copy was retained unused. Do not point new registration back there. Frida's optional install script was not enabled; static Ghidra use does not need it.
