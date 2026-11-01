# XDisplay protocol observations

Notes updated 2026-11-01 for the 2026-10-31 Windows experiment: process/device/endpoint evidence includes one cable disconnect/reconnect cycle. No USB or application payload capture, message framing, codec, encryption, or iPad application endpoint has been established. Follow `WINDOWS-CODEX-HANDOFF.md` when older project notes conflict.

Private run: `C:\Users\noobieGG\HASHI-private\runs\20261031-184820`. Binary identities and component roles are recorded in `docs/windows-components.md`. All times below are Asia/Calcutta, UTC+05:30. These findings use PowerShell 7.6.5 and Windows CIM/network queries, not REA decompilation.

## WIN-OBS-001: observed host communication boundary

**Question:** Which process is a useful first candidate for iPad-session transport analysis?

**Classification: Fact.** In the 18:52:01–18:52:05 connected snapshot, `SWXDAgent.exe` PID 20696, session 1, has `libusbmuxd.dll` loaded and an established loopback socket `127.0.0.1:55435` ↔ `127.0.0.1:27015`. The reciprocal endpoint belongs to Apple Mobile Device Service PID 8920, which also has a listener on 27015. The agent is x86, product version `1.5.8.3`, file version `1.58.9.6924`, SHA-256 `CB9AB63BE48947344E6D0E5E718E5522E707C64473DAC6CC026149424964E52C`. The loaded `libusbmuxd.dll` SHA-256 is `F198C3649D934FE6DC1004541D06844348009D792EA02FBB79D706EF30FDEDA3`.

**Method and location:** `scripts/Get-WindowsBaseline.ps1`; `Win32_Process` filtered by the recorded process names/path, `Get-Process.Modules` filtered by vendor/Apple path, and `Get-NetTCPConnection` filtered by the selected PIDs. Evidence: `baseline-B-preparing/processes.json`, `modules.json`, `tcp.json`. TCP state 5 represents Established; listener state is 2. No instruction address or packet/frame number applies to this endpoint snapshot.

**Inference:** The agent is a local client of Apple Mobile Device Service and is the leading process for transport investigation. The listener and reciprocal endpoint support this direction; connection initiation itself was not recorded.

**Fact:** A second connected-state snapshot, `baseline-C-check` at 18:53:41–18:53:45, returned the same established endpoint pair and agent-loaded `libusbmuxd.dll`. This repeats the observation while connected; it does not establish cable-transition behavior.

**Limitations:** This may be a persistent device-notification/control connection rather than the application data stream. A loaded library does not identify the function executing socket operations. Port 27015 is the observed Windows loopback endpoint, not a proven iPad-side application port. USB transport, usbmux messages, application messages and video frames remain distinct unknown layers.

**Hypothesis, tested once:** This agent↔Apple connection might persist through cable removal as a discovery/control channel. **Observation:** WIN-OBS-003 records its disappearance with the agent still running. Persistence is not supported for this connection in this disconnect trial. The result still does not distinguish application data from a device-bound control channel.

## WIN-OBS-002: connection preparation and display state

**Question:** What changed between the initial and connected snapshots?

**Classification: Fact.** At 18:49:34–18:49:37 (`baseline-A`), the selected device list contained no Apple/iPad entry, the filtered process list contained no `SWXDAgent.exe`, and LuminonCore's current resolution was null. Apple Mobile Device Service and Bonjour were already running; Apple service was already listening on loopback 27015.

**Classification: Fact.** At 18:52:01–18:52:05 (`baseline-B-preparing`), the selected present-device list contains Apple iPad, Apple Mobile Device USB Device, Apple Mobile Device USB Composite Device and `Generic Monitor (XDISPLAY)`, all reported OK. The LuminonCore adapter reports 1280×960, with the AMD adapter at 1920×1200. Apple USB devices are associated with Apple provider version `538.0.0.0`, INF `oem4.inf`.

**Classification: Fact.** Follow-up current device properties identify `WINUSB` as the Apple Mobile Device USB Device service and `usbccgp` as the Composite Device service (`apple-active-properties.json`). This does not prove the application's framing or identify the entire loaded filter stack.

**Limitations:** Starting the host app and connecting the iPad occurred between the snapshots, so this comparison changes more than one variable. It cannot isolate cable insertion from process launch or app state. The monitor/resolution data alone do not establish mode or image correctness. **Fact (user report):** The user subsequently stated the iPad showed a working extended display before unplugging (`user-observation-disconnect.json`, recorded 18:57:34). iPad app version, iPadOS version and exact attach time remain unknown. WUDFHost PID 13584 appeared, but its driver ownership is unknown.

**Next validation:** Repeat the disconnect/reconnect cycle recorded in WIN-OBS-003/004 with the agent left running. The current evidence contains one cycle, not multiple independently repeated cycles.

## WIN-OBS-003: cable removal with the agent retained

**Question:** Does the observed agent↔Apple socket survive cable removal when the agent remains running?

**Classification: Fact (user report).** The user reported: “disconnected - ipad was showing a working display that was extended.” The report was retained at 18:57:34.093 in `user-observation-disconnect.json`; the exact physical removal time is unknown.

**Classification: Fact.** The finalized `connection-watch.jsonl` sample 24 beginning 18:56:53.162 and ending 18:56:54.207 contains the Apple/XDISPLAY devices and established socket `55435`↔`27015`. Sample 25 beginning 18:56:56.225 and ending 18:56:57.241 contains no Apple/XDISPLAY device entries and no agent TCP entry, while agent PID 20696 and Apple service PID 8920 remain present. Apple's 27015 listener remains. The independent `baseline-D-disconnected` snapshot at 18:57:30.019–18:57:34.051 confirms these conditions.

**Method/location:** Repeated process, present-device and TCP snapshots; the two JSONL records are selected by their one-based sample indices and `Started` timestamps. `baseline-D-disconnected/processes.json`, `devices.json` and `tcp.json` retain the confirming state. No packet capture or call trace was collected. The watch is finalized with 64 samples and its SHA-256 is recorded below.

**Inference:** This particular connection's lifetime is associated with the connected device/session, rather than merely the host process lifetime. One removal trial does not establish which protocol messages or payloads it carried, exact event ordering, or repeatability.

**Classification: Fact.** `baseline-D-disconnected/displays.json` still reports LuminonCore 1280×960 after the XDISPLAY monitor is absent from the present-device list. **Inference:** `Win32_VideoController` resolution can represent stale/configured state here and is insufficient to establish an active display image.

**Next validation:** Reconnection is recorded in WIN-OBS-004. Repeat this removal/reconnect cycle, then use a separate bounded payload or call observation to distinguish device-bound control traffic from session data.

## WIN-OBS-004: reconnect under the same process IDs

**Question:** Does the agent recreate the observed local Apple-service connection when the device returns?

**Classification: Fact.** Watch sample 54 (18:58:17.067–18:58:17.780) still has no Apple/XDISPLAY devices or agent TCP connection. Sample 55 (18:58:19.785–18:58:20.825) has both Apple USB device entries, the XDISPLAY monitor and a new established `127.0.0.1:60785` ↔ `127.0.0.1:27015` socket pair. Agent PID 20696 and Apple service PID 8920 are unchanged. The Apple iPad WPD entry returns in sample 57 (18:58:25.858–18:58:26.830). Device-query ordering and sampling delays do not establish USB-protocol event order.

**Classification: Fact.** `baseline-E-reconnected` (18:58:42.197–18:58:47.520) independently confirms the returned device entries, same process IDs and socket pair. The user replied “connected” to the prompt “Reconnect the same cable and reply when extended display returns”; the exact response and prompt are retained at 18:58:47.559 in `user-observation-reconnect.json`. This contextual report supports display restoration but is not an independently captured image.

**Inference:** The observed agent↔Apple connection is recreated across this device/session transition, with a newly selected local ephemeral port. This strengthens the choice of the agent↔Apple boundary for focused analysis. The sample set establishes one cycle only; it does not establish a stable device-side port, video codec, payload role or the general handshake.

**Method and locations:** Compare semantic sets of process IDs, device names and socket tuples, ignoring row ordering. One-based JSONL sample numbers refer to the finalized 64-record file. The observation spans 18:55:47.730–18:58:47.228, with these changes:

| Sample | Query interval, UTC+05:30 on 2026-10-31 | Observed state |
| --- | --- | --- |
| 1–24 | First sample begins 18:55:47.730; sample 24 ends 18:56:54.207 | Four selected device entries, agent socket local port 55435. |
| 25–54 | Sample 25 begins 18:56:56.225; sample 54 ends 18:58:17.780 | No selected Apple/XDISPLAY devices or agent socket; both processes and Apple listener persist. |
| 55–56 | Sample 55 begins 18:58:19.785; sample 56 ends 18:58:23.856 | Two Apple USB entries and XDISPLAY monitor return; new agent local port 60785. |
| 57–64 | Sample 57 begins 18:58:25.858; sample 64 ends 18:58:47.228 | Apple iPad WPD entry also returned; new socket remains established. |

**Next validation:** Repeat one controlled cable cycle, then test a static image versus a small image update using a bounded recording or focused call observation. Correlate any new data with these observed endpoints without treating TCP, USB, usbmux and video boundaries as interchangeable.

## Initial experiment record

| Field | Recorded state |
| --- | --- |
| Experiment | `WIN-BASELINE-01`, 2026-10-31 UTC+05:30 |
| Purpose | Establish initial process, module, device, display and socket evidence before payload analysis. |
| Starting state | No Apple/iPad device returned by the filtered present-device query; agent absent from filtered process query. Trust/pairing status and physical cable state were not separately observed. |
| Setup | Sequential read-only snapshots into `baseline-A`, `baseline-B-preparing`, `baseline-C-check`, `baseline-D-disconnected` and `baseline-E-reconnected`, plus finalized 64-sample `connection-watch.jsonl`; no USB/desktop-frame capture. |
| Timeline | Initial snapshot 18:49:34.051–18:49:37.891; user later agreed to open XDisplay and connect the iPad; connected snapshot 18:52:01.182–18:52:05.335; first sampled disconnected state 18:56:56.225–18:56:57.241; confirming disconnected snapshot 18:57:30.019–18:57:34.051; first sampled new socket/USB/monitor state 18:58:19.785–18:58:20.825; confirming reconnected snapshot 18:58:42.197–18:58:47.520. Exact physical action times not retained. |
| Outcome | Agent↔Apple socket and Apple/XDISPLAY devices disappeared after user-reported removal, then returned after reconnect with agent local port changed from 55435 to 60785; both main process IDs and Apple's listener persisted. User reported a working extended image before removal and replied “connected” when asked to report its return. LuminonCore's resolution property remained 1280×960 even while disconnected. |
| Repeatability | One disconnect/reconnect cycle observed, with snapshots corroborating the sampled states. Multiple-cycle repeatability remains untested. |
| Cleanup | Queries made no pairing/driver/configuration changes. The user controls the cable and app state. |
| Unknown | Mirror-mode behavior, independently captured image correctness, actual session traffic, function ownership, device-side endpoint and application protocol. |

## Evidence identity

Hashes identify the original JSON evidence files, not packet captures. Originals remain in the private run directory.

| Relative evidence file | SHA-256 |
| --- | --- |
| `baseline-A/snapshot.json` | `16F7E004026134B8F522307BAA3F8A8D3329C01670DEF284AF96A1DCDF9C1720` |
| `baseline-A/processes.json` | `8BBBBC28F8188E2C9115AB0DF42910020B499B22B009BD85274880770A918CD9` |
| `baseline-A/tcp.json` | `5590C04A4BB4B0ABC0F0BAD0614E5F076A19407D6E7E918D4A7E5BDD225C0EA5` |
| `baseline-B-preparing/snapshot.json` | `40FC89B20C7A9A84568DB0CC149FD719055347293A69BC89FC028B357AE30E6E` |
| `baseline-B-preparing/tcp.json` | `D8D8495BC5700DBC834812A39127127B6C65AB53B366E34B01AD14102767BB56` |
| `baseline-B-preparing/devices.json` | `0B254BBB322F6DB2B1A7837A4C8A4A32CFA287CB6F9D66CEA325DB2FB77F2362` |
| `baseline-B-preparing/displays.json` | `B50FD89ADF8A76A2F82BD8AA1215B992162A79DD69036E8AB53E7FC19484250D` |
| `baseline-C-check/tcp.json` | `D6ED00D35CAEB25E379C026448F8B9000144501F63148C6F10215A6DF51E2368` |
| `apple-active-properties.json` | `953B92D1656A8DD4440E3483DA0FA7352AD3E42427821A8E46C147292D616130` |
| `user-observation-disconnect.json` | `E54BEE78E9AD550B3BEE6AA09852A8E6B1FAA032E835F2530333249E0D1F94A8` |
| `baseline-D-disconnected/snapshot.json` | `A2BE7F6CE70CF6C278A7AF70B980A37D4D57D73AE09D3BB14D697A61DF329C8D` |
| `baseline-D-disconnected/devices.json` | `E530D38F3E1F688EFB79FC8B7F0EF5098FA35FBD9B59F2EFF081B6C90A68D639` |
| `baseline-D-disconnected/tcp.json` | `1A1DDBC65EED1601DD5E2DD0612C1CCC3CEF4D58600135555FE93EADC83BF149` |
| `baseline-D-disconnected/displays.json` | `B50FD89ADF8A76A2F82BD8AA1215B992162A79DD69036E8AB53E7FC19484250D` |
| `user-observation-reconnect.json` | `9224D32B36764F98EC76D23316EE029074DB53FA73FF609B9ADB6A44121D0E2A` |
| `baseline-E-reconnected/snapshot.json` | `1B52D31A9AA7FCF773AF670BADFA54CC7E78FACF182ED31309922B6A258E8548` |
| `baseline-E-reconnected/devices.json` | `0B254BBB322F6DB2B1A7837A4C8A4A32CFA287CB6F9D66CEA325DB2FB77F2362` |
| `baseline-E-reconnected/tcp.json` | `7250CE7CFF9FFAF0A109D8BE442CE2DE95F80412970CB78CDB0A1ECBABCB8CFF` |
| `connection-watch.jsonl` (finalized, 64 samples) | `F0D1F1B7F0F2DB9A316F62924D91A97EABA08BF12D48CA8CE39E51A3CD2D18F9` |

## Protocol fields still unknown

No candidate application message has yet been justified. Device-side port/channel, handshake sequence, length/type fields, byte order, image codec, compression/encryption, frame boundaries, resolution negotiation and input events remain unknown. Installed codec/library names and a Windows loopback socket do not fill these fields.

The next protocol question is whether the observed device/session-associated socket is control only or also carries session data. Repeat the cable-cycle observation, then correlate a bounded recording or focused call observation with one controlled image update. Keep raw payload evidence and decompilation outside the source workspace.
