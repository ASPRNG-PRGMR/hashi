# Windows XDisplay component inventory

## Return verification — 2026-11-03

[Windows return investigation](windows-return-investigation.md) records current installed/restored binary hashes, agent PID 26580, Apple-service PID 9976, actual module bases and loaded Winsock IAT resolution. **Fact:** These vendor hashes match the earlier x86 artifacts. Agent base 0x00cc0000 and libusbmuxd base 0x73c90000 are observed for this process instance only; rederive live addresses next time. The display installation was preserved.

Experiment recorded 2026-10-31, Asia/Calcutta (UTC+05:30); notes updated 2026-11-01. The corrections and priorities in `WINDOWS-CODEX-HANDOFF.md` govern this inventory. This document summarizes local observations; it contains no vendor code or device identifiers.

Private evidence root for this run: `C:\Users\noobieGG\HASHI-private\runs\20261031-184820`. Paths below that root are evidence references, not files to add to the source workspace. Binary identities were measured at approximately 18:51:05 using `scripts/Get-BinaryIdentity.ps1`; its PE-header checks determine architecture and preferred image base, and `Get-FileHash -Algorithm SHA256` determines identity. File versions are embedded metadata, not independently verified release history.

## Processes and relationships

**Fact:** The initial snapshot (`baseline-A`, 18:49:34–18:49:37) found Apple Mobile Device Service PID 8920, Bonjour PID 8960, and Splashtop Software Updater PID 9340 running. The filtered process list did not contain `SWXDAgent.exe`; the present-device list contained the two LuminonCore devices but no Apple/iPad device.

**Fact:** The connected snapshot (`baseline-B-preparing`, 18:52:01–18:52:05) found `SWXDAgent.exe` PID 20696, parent PID 7328, session 1, at `C:\Program Files (x86)\Splashtop\Splashtop Wired XDisplay\Agent\SWXDAgent.exe`. Its identity is x86/PE32, despite the x64 operating system and x64 display drivers. The product version is `1.5.8.3`; its separate file version is `1.58.9.6924`.

| Component | Classification and observed role | Remaining limitation |
| --- | --- | --- |
| `SWXDAgent.exe` | **Fact:** Running process with a loopback connection to Apple Mobile Device Service. **Inference:** Leading host communication-process candidate. | UI ownership, call paths, and application payload responsibilities have not been established. |
| `libusbmuxd.dll` | **Fact:** Present in the agent directory and loaded in PID 20696. | A loaded module is not proof that a particular exported function ran. |
| `libplist.dll`, `libxml2.dll`, `libiconv.dll` | **Fact:** Loaded in PID 20696 in the connected snapshot. | Specific parsing/transport responsibilities remain unknown. |
| `AdbWinApi.dll`, `AdbWinUsbApi.dll` | **Fact:** Loaded in PID 20696 alongside the Apple-related evidence. | Loading these Android-related candidates does not establish their involvement in this iPad session. |
| `libimobiledevice.dll` | **Fact:** Installed beside the agent. | Not returned by the filtered module enumeration in this snapshot; no claim of runtime use or lifetime-wide absence. |
| `SRx264Wrapper.dll`, `libx264-116.dll` | **Fact:** Installed beside the agent. **Hypothesis:** Encoding helpers; test by observing module loads/call paths during an active display stream. | Wire codec, active use, and buffer format remain unproved. |
| `SRDxgiCaptor.dll` | **Fact:** Installed beside the agent. **Hypothesis:** Capture helper; test by observing module loads and callers in each display mode. | Filename alone does not establish the capture API or mirror/extended-mode ownership. |
| `lci_iddcx.dll` | **Fact:** x64 DLL at `C:\Windows\System32\drivers\UMDF\lci_iddcx.dll`, associated INF examined below. | The particular `WUDFHost.exe` loading it has not been identified. |
| `lci_proxywddm.sys` | **Fact:** x64 driver at `C:\Windows\System32\drivers\lci_proxywddm.sys`, associated INF examined below. | Exact kernel/IPC responsibilities are unknown. |
| Apple Mobile Device Service | **Fact:** PID 8920, session 0, running from `C:\Program Files\Common Files\Apple\Mobile Device Support\AppleMobileDeviceService.exe`; listening on loopback port 27015. | The socket is a local host endpoint, not an established iPad application port. |
| Bonjour | **Fact:** PID 8960, session 0, running from `C:\Program Files\Bonjour\mDNSResponder.exe`; loopback connections with Apple service on port 5354. Agent also loaded `C:\Program Files (x86)\Bonjour\mdnsNSP.dll`. | These observations do not prove Bonjour is required for XDisplay's USB session. |
| Splashtop Software Updater | **Fact:** `SSUService.exe`, PID 9340, session 0, running from the separate Splashtop Software Updater directory. | No session payload role established. |

**Fact:** The observed established socket pair was `127.0.0.1:55435` (PID 20696) ↔ `127.0.0.1:27015` (PID 8920). The Windows TCP-state value is 5 (Established); PID 8920 also had a listener, state 2, on 27015. **Inference:** The agent is a local client of the Apple service. Connection initiation was not captured, so the endpoint roles are supported by the listener and socket pairing rather than a recorded SYN exchange.

**Fact:** Following the user's cable-disconnect report, `baseline-D-disconnected` (18:57:30–18:57:34) still contains agent PID 20696 and Apple service PID 8920, but no agent TCP endpoint or Apple/XDISPLAY present-device entry. Apple service's loopback 27015 listener remains. The finalized `connection-watch.jsonl` first records this changed state in sample 25 beginning 18:56:56.225; sample 24 beginning 18:56:53.162 still contains the devices and socket. These are sequential query intervals, not exact removal or socket-close timestamps.

**Fact:** In watch sample 55 (18:58:19.785–18:58:20.825), the same agent PID 20696 has an established connection with a new local port, `127.0.0.1:60785` ↔ Apple PID 8920 at `127.0.0.1:27015`. The two Apple USB devices and XDISPLAY monitor are present again. The Apple iPad WPD entry reappears in sample 57 (18:58:25.858–18:58:26.830). `baseline-E-reconnected` (18:58:42–18:58:47) confirms all four device entries and the new socket pair. **Fact (user report):** The user replied “connected” to the request to report when the extended display returned. One disconnect/reconnect cycle is observed; repeated cycles have not yet been tested.

## Driver associations

**Fact:** `Win32_PnPSignedDriver` associates the LuminonCore IDDCX Adapter with `oem1.inf` and the LuminonCore WDDM PROXY with `oem2.inf`, both provider `LuminonCore`, version `1.0.2018.1204`. These names were rediscovered on this installation; they are not portable package identities.

**Fact:** The retained `oem1.inf` names `lci_iddcx.dll`, `UmdfLibraryVersion=2.15.0`, `UmdfExtensions=IddCx0102`, `AddService=WUDFRd`, and upper filter `IndirectKmd`. It records device group `IddSampleDriverGroup`. **Inference:** This is a UMDF/IddCx display-driver arrangement. Neither the binding identifier nor the device-group string proves a particular IddCx API version or shared source with Microsoft's sample.

**Fact:** The retained `oem2.inf` names service `lci_proxywddm` with `ServiceBinary=%12%\lci_proxywddm.sys`; its installed service definition is a kernel driver. No driver disassembly or frame-handoff evidence is included here.

**Fact:** In the connected snapshot, both Apple Mobile Device USB Device and Apple Mobile Device USB Composite Device are associated with provider `Apple, Inc.`, version `538.0.0.0`, published INF `oem4.inf`. Follow-up device-property queries (`apple-active-properties.json`) identify service `WINUSB` for the USB Device and `usbccgp` for the Composite Device. The retained `oem4.inf` includes `winusb.inf`/`WINUSB.NT` and `usb.inf`/`Composite.Dev.NT` service arrangements, plus Apple filter-service declarations. The exact loaded filter stack has not been observed.

**Fact:** Separately, the installation directory `C:\Program Files\Common Files\Apple\Mobile Device Support\Drivers` contains `usbaapl64.inf`, `usbaapl64.sys`, its catalog and resource DLL. This bundled-directory listing does **not** identify the active device stack: the current device properties above identify WINUSB/usbccgp. `AppleSSD.sys` supplies no evidence for this transport.

**Fact:** The connected present-device list contains an Apple iPad, two Apple USB device entries, and `Generic Monitor (XDISPLAY)`, all reported OK. `Win32_VideoController` reports LuminonCore at 1280×960 and the AMD adapter at 1920×1200. The initial snapshot had no current LuminonCore resolution. **Fact (user report):** The user reported that the iPad showed a working extended display before unplugging, retained in `user-observation-disconnect.json` at 18:57:34. This is attributed visual confirmation, not an independently captured desktop image.

**Fact:** `baseline-D-disconnected/displays.json` still reports LuminonCore at 1280×960 after the Apple devices and XDISPLAY monitor disappear from the present-device query. **Inference:** This resolution property can retain stale or configured state and must not be used alone as proof of an active image or connected display. Mirror mode has not been tested.

## Binary identities

All agent-directory rows below use `C:\Program Files (x86)\Splashtop\Splashtop Wired XDisplay\Agent`. Hashes identify the inspected installed files, not an assertion about every distribution bearing the same version.

| Binary | Architecture | File / product version | SHA-256 |
| --- | --- | --- | --- |
| `SWXDAgent.exe` | x86 | `1.58.9.6924` / `1.5.8.3` | `CB9AB63BE48947344E6D0E5E718E5522E707C64473DAC6CC026149424964E52C` |
| `libusbmuxd.dll` | x86 | `1, 0, 10, 5` / same | `F198C3649D934FE6DC1004541D06844348009D792EA02FBB79D706EF30FDEDA3` |
| `libimobiledevice.dll` | x86 | `1, 0, 10, 5` / same | `3807BB893C35513B81F5185AB8EECFF1CA3F8569F51A244C4A1C5A689774BF6C` |
| `SRx264Wrapper.dll` | x86 | `1.58.9.6924` / `1.5.8.3` | `58F5AAC522316BAB39F5A727344721485AB6F8A8BD3068B7918CEA4CB22EB98C` |
| `libx264-116.dll` | x86 | No version returned | `246632D6B2F07C3A7E8B5ABAC796C6FF13CD71548D946C59359E9DC2502A7D33` |
| `SRDxgiCaptor.dll` | x86 | `1.58.9.6924` / `1.5.8.3` | `A0D5EDEEBE9D8D69AA0588BFEF408CE2297D2E71A6A2959F76AEE6416616BEBD` |
| System UMDF `lci_iddcx.dll` | x64 | `1.0.2018.1204` / same | `148359A84C637D05C20A58F5038D8B2C5390F99A5A229BE8ECCBB5F85E969438` |
| System driver `lci_proxywddm.sys` | x64 | `1.0.2018.1204` / same | `0F1C64C0FA08FE45BEAC15DC675D3B956525B8F198E92E0CCAC21D2A70CE42CF` |
| `AppleMobileDeviceService.exe` at the service path above | x64 | `560.60.2.13` / blank | `59B363272FC262EE0BD3C830D065BD934A0A81A8B03B1922B9F93B60076F7947` |

**Fact:** PE-header preferred image bases/entry RVAs are `0x400000`/`0x137917` for the agent, `0x10000000`/`0x4214` for `libusbmuxd.dll`, `0x180000000`/`0x5440` for the UMDF DLL, and `0x140000000`/`0x1c12c` for the kernel driver. These are static PE values, not observed runtime addresses or analyzed function boundaries. No function-level semantic claim has been made.

## Evidence and reproducibility

Use `scripts/Get-WindowsBaseline.ps1 -OutputDirectory <new-private-directory>` for each new state. Its source records the process-name/path, service, provider and present-device filters; TCP entries are limited to the matching PIDs. It reads sequentially, so a snapshot is not an atomic event trace. Use a fresh directory to preserve the earlier states.

Private evidence identities:

| Relative evidence path | SHA-256 |
| --- | --- |
| `binary-identities.json` | `C590C75AADC02FCA07C1BF752963AFCD6BA58ED78CB2F2ABF0A90BD9ADCEC989` |
| `oem1.inf` | `60A018F46D17B7640FC34587667CD852A16FA8E82F957A69522637F22E5FE5CF` |
| `oem2.inf` | `D10FA136D6AE9A15216202E4DD9F787B3A148213569E438DA3BF82B618D8001D` |
| `oem4.inf` | `71EF7DBEF3E7B2C1BDC32C1A4400AA5F92C5C7EEE9EF6261385C54CD9D0E26A6` |
| `apple-active-properties.json` | `953B92D1656A8DD4440E3483DA0FA7352AD3E42427821A8E46C147292D616130` |
| `baseline-B-preparing/processes.json` | `5E3223D022CFEA60D0E855ACE77D284223A24E6FC5E1FA6963F3F91FFDE6D176` |
| `baseline-B-preparing/modules.json` | `6DA3CBDA7FD8E483FA9DC80265A282C5E06A39A94857254BBAFB1E22E70DAE7D` |
| `baseline-B-preparing/drivers.json` | `2C29EB188931D6C9DF7472D0D1E75DB1A7058E672096AA0BA133D66E661D4D31` |
| `user-observation-disconnect.json` | `E54BEE78E9AD550B3BEE6AA09852A8E6B1FAA032E835F2530333249E0D1F94A8` |
| `baseline-D-disconnected/devices.json` | `E530D38F3E1F688EFB79FC8B7F0EF5098FA35FBD9B59F2EFF081B6C90A68D639` |
| `baseline-D-disconnected/tcp.json` | `1A1DDBC65EED1601DD5E2DD0612C1CCC3CEF4D58600135555FE93EADC83BF149` |
| `user-observation-reconnect.json` | `9224D32B36764F98EC76D23316EE029074DB53FA73FF609B9ADB6A44121D0E2A` |
| `baseline-E-reconnected/tcp.json` | `7250CE7CFF9FFAF0A109D8BE442CE2DE95F80412970CB78CDB0A1ECBABCB8CFF` |
| `connection-watch.jsonl` (finalized, 64 samples) | `F0D1F1B7F0F2DB9A316F62924D91A97EABA08BF12D48CA8CE39E51A3CD2D18F9` |

**Limitation:** The initial module collector did not reliably distinguish an unavailable/empty module enumeration from no matching modules. Null process paths and the absent WUDF module records cannot establish absence of `lci_iddcx.dll`. The collector was subsequently corrected to record a missing module enumeration explicitly. In `baseline-C-check` (18:53:41–18:53:45), WUDFHost PIDs 2044, 4508, 4796 and 13584 all report no modules returned; access may be restricted. None is attributed to XDisplay without its loaded-module evidence. The same connected agent↔Apple socket pair and agent-loaded `libusbmuxd.dll` were observed again; this is a repeated connected-state observation, not a disconnect/reconnect experiment.

**Next validation:** Repeat the cable transition with the same agent process, then use a bounded payload/call observation and a simple test image to identify whether the observed socket carries control or application data. Inspect the active Apple filter stack only if needed for transport capture, and obtain a permitted loaded-module view of the specific UMDF host. Prioritize the observed agent↔Apple boundary before broad driver reversing.
