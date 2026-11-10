# WIN-NEXT-02: startup stream and observed framing

Updated 2026-11-05 (Asia/Calcutta). Event times are UTC unless stated otherwise. This is the current Windows capture result for the Fedora transfer. Read the prior return and source-correlation reports for preserved negative trials and artifact provenance.

## Result

**Fact:** One bounded attachment captured connection establishment, the complete observed application startup exchange in both directions, and 1,903 image records on the same returned socket. Twelve selected JPEG buffers from that stream matched independently measured white → black → white screen pixels. The user confirmed both changes completed and the display still worked.

**Fact:** Every completed send/recv in the selected Apple-loopback scope was retained in full. No copy errors, truncation, capture-limit hits, negative/partial returns, recorded overlapping I/O, event gaps, or script/cleanup errors were observed. This is complete within the selected APIs, endpoint and time window; it is not an assertion about every possible application transport or mode.

**Fact:** Both captured application streams parse exactly as a one-byte tag followed by a three-byte big-endian payload length and that many payload bytes. The outgoing stream contains one tag-4 record of length zero, three tag-5 records of length 12, and 1,903 tag-6 JPEG records. The incoming application stream contains one tag-4 record of length zero and three tag-5 records of length 12. Both parsers end exactly at the captured stream end.

**Inference:** This is an evidence-backed framing rule for the recorded session. Tag-6 content is established as JPEG in this session; the semantics of every startup field, all tag values, all operating modes and a complete interoperable protocol remain unestablished. No speculative host protocol was implemented.

The Windows capture work planned for this transfer is complete. Fedora can now perform offline stream validation, targeted static analysis and implementation of validated parsing. Further Windows experiments should be driven by a specific uncovered behavior, not by repeating setup.

## Identity, connection and scope

Private run **T**: `<private-evidence-root>/runs/startup-20261105-103819`, outside this checkout.

Evidence IDs WIN-START-E001–E005 are local investigation identifiers. The observation used the existing Frida 17.23.2 Node binding, PowerShell/.NET screen checks and independent analysis scripts. No Ghidra reinstall, driver or pairing change was performed.

**Fact:** User-selected SWXDAgent PID 22412 was running before attachment; the iPad/XDISPLAY device entries and agent Apple socket were absent. Installed hashes matched the studied artifacts:

| Artifact | SHA-256 |
| --- | --- |
| SWXDAgent.exe | cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c |
| libusbmuxd.dll | f198c3649d934fe6dc1004541d06844348009d792ea02fbb79d706ef30fdeda3 |

| Runtime item | Observed value |
| --- | --- |
| Agent / Apple service PID | 22412 / 9768 |
| Agent / libusbmuxd / WS2_32 base | 0x00b50000 / 0x74c60000 / 0x75db0000 |
| usbmuxd_connect argument device / port | 1 / 6789 (0x1a85) |
| x86 argument bytes | 01 00 00 00 85 1a 00 00 |
| Agent connect call / return | RVA 0x30c9c / 0x30ca1; VA 0x00b80c9c / 0x00b80ca1 |
| Returned socket | EAX 0x4c0 = 1216, generation 3 |
| Session tuple | 127.0.0.1:55873 → 127.0.0.1:27015 |
| First application send | Agent return RVA 0x30478, 05:11:18.384Z |
| Ongoing header / payload calls | RVAs 0x2f702 / 0x2f718; return RVAs 0x2f708 / 0x2f71e |
| First captured JPEG payload | Event 82, 05:11:19.490Z |

**Fact:** The observer was ready at 05:10:01.412Z, before the requested cable connection. usbmuxd_connect entered at 05:11:18.381Z and returned at .383Z, event 48/call ID 11/thread 24940. The numeric handle 1216 was reused across three connection generations with source ports 55866, 55872 and 55873. Streams are separated by generation, socket, local port and direction; numeric-handle equality alone is insufficient.

**Fact:** The generation-3 outgoing usbmux control exchange occupies bytes [0,592); its incoming Result exchange occupies [0,294). The captured Connect plist has DeviceID 1 and PortNumber 34074 (0x851a); the call's argument was 6789 (0x1a85). This byte swap is consistent with the earlier static htons call. Result Number is 0. Earlier generations contain ListDevices exchanges. Device identifiers and raw plist content remain private.

## Complete observed application startup

Offsets are relative to the generation-3 direction file, after the usbmux portion. Hex below records protocol observations; command names/meanings are deliberately not invented.

| Order | Direction / offset | Tag / length | Payload hex | Direct observation |
| --- | --- | --- | --- | --- |
| 1 | Host→iPad / 592 | 4 / 0 | empty | Four bytes 04000000 sent at return RVA 0x30478. |
| 2 | iPad→host / 294 | 4 / 0 | empty | Four bytes 04000000 received at RVA 0x112ee. |
| 3 | Host→iPad / 596 | 5 / 12 | 000000010000000000000000 | One 16-byte send at RVA 0x30592. |
| 4 | iPad→host / 298 | 5 / 12 | 000000020000080000000600 | One 16-byte receive; mechanical BE32 grouping gives 2,2048,1536. |
| 5 | Host→iPad / 612 | 5 / 12 | 000000fe0000000000000000 | One 16-byte send at RVA 0x306e7. |
| 6 | iPad→host / 314 | 5 / 12 | 000000ff0000000000000000 | One 16-byte receive. |
| 7 | Host→iPad / 628 | 5 / 12 | 000000fc0500000000000000 | One 16-byte send at RVA 0x30837. Do not assume uniform BE32 field semantics: bytes 05 00 00 00 need independent interpretation. |
| 8 | iPad→host / 330 | 5 / 12 | 000000fd0000000000000000 | The four-byte header and twelve-byte body arrived in separate recv calls. |
| 9 onward | Host→iPad / 644 | 6 / variable | JPEG payload | 1,903 records through stream end. |

**Fact:** The final 16-byte response being split into recv lengths 4 and 12 demonstrates why API-call boundaries cannot be treated as application-message boundaries. No packet capture was performed; the files reconstruct accepted Winsock byte streams using captured chunk offsets. Recorded concurrent same-direction calls did not overlap in this window. This does not measure physical USB transfer boundaries or packet retransmissions.

**Resolved by FED-START-E001 (2026-11-07):** these are the client dimensions. `CProbeUsbmuxd::DoHandshake` at RVA `0x303f0` requires HELLO ACK field 0 to equal 2, then reads field 1 as the client width and field 2 as the height, aligns each as `((v - 1) & ~3) + 4`, and stores them to shared state `+0x14`/`+0x18`, logging `client resolution (%d, %d) -> (%d, %d)`. The earlier hypothesis is confirmed and the semantic role is now established. Two other observations in this report are also explained there: the little-endian `05 00 00 00` field is written with no `htonl` unlike every sibling field, and the final reply's 4-plus-12 receive split is by design rather than a network artifact. See [startup handshake](fedora-startup-handshake.md).

## Framing and image validation

**Fact:** For every one of the 1,903 adjacent header/payload send pairs, header bytes 1–3 interpreted as an unsigned big-endian integer equal the actual successful payload-send length. Byte 0 is 6 throughout the image sequence. Parsing the concatenated stream independently with that rule consumes all records with no trailing or missing bytes. The first image header is 06 00 4d 73, followed by 19,827 payload bytes.

**Fact:** Static instructions in FED-E005's agent-send-candidate.asm at agent RVAs 0x2f6c5–0x2f6ee shift the payload length, optionally transform byte order, and combine a byte-sized value before the direct header send. This corroborates the observed format. The alternate branch and its selection conditions are not established for all sessions; the captured session supports the BE24 branch only.

**Fact:** Every tag-6 payload has JPEG SOI/EOI markers and a parsed SOF0 header declaring 8-bit, three-component, 1280×960 content. Twelve selected records were fully decoded with System.Drawing.Bitmap. All 49 sampled interior-square points per selected image matched the expected white or black value. The same socket generation carries the captured startup and these images, closing the earlier cross-session evidence limitation for this experiment.

The automatic pattern logged baseline at 05:11:26.057Z, white→black at 05:11:36.079Z, black→white at 05:11:46.081Z and finish at 05:11:56.070Z. Six local desktop probes checked physical secondary bounds (1920,0),1280×960, a 160×160 square at (100,100), and the #202020 background. Each probe passed. The user confirmed the visible pattern during and after the run.

Selected white payloads were 26,568 bytes; selected black payloads were 26,408 bytes early and 26,180 bytes late. Pixel correspondence is established; constant whole-image bytes, fixed frame rate, encoding settings, input events, alternate resolutions and modes are not inferred from these lengths.

## Completeness, cleanup and hashes

**Fact:** The trace contains 11,495 consecutive events and 3,827 completed I/O chunks, totaling 130,378,071 captured accepted bytes across all six direction files. The per-call 2 MiB and total 512 MiB capture caps were not reached. All chunks match their accepted lengths, stream offsets are contiguous, and file sizes equal chunk sums. No matching WSASend/WSARecv calls were observed; the hooks do not constitute general overlapped-completion coverage.

**Fact:** The generation-3 outgoing file is 130,375,769 bytes: 592 bytes usbmux control, then 130,375,177 application bytes (1,907 records). The incoming file is 346 bytes: 294 bytes usbmux reply, then 52 application bytes (four records). Complete within this bounded observation does not mean a complete protocol across modes, errors, reconnection, touch input or session shutdown.

**Fact:** Hooks were removed, the script unloaded and the session detached at 05:11:58.242Z with no pending recorded calls or cleanup errors. The user replied “Both changes completed; display works.” The post-test sequential baseline ran at 10:44:25.799–10:44:29.997 +05:30. The working installation was preserved.

| ID | Evidence |
| --- | --- |
| WIN-START-E001 | Before/after baselines, artifact hashes, user confirmations |
| WIN-START-E002 | Full trace, direction streams, observer/runner and test-action logs |
| WIN-START-E003 | Startup analysis and its reproducible script |
| WIN-START-E004 | Extracted controlled samples, decoder and pixel correspondence |
| WIN-START-E005 | Whole-application stream parser and record ledger |

| File relative to T | SHA-256 |
| --- | --- |
| evidence-index.json | dc5eff1ce1cc610a44ecc33d6f1c290a82551f30e5a73defa10f16bf2b63af52 |
| trace.jsonl | 3f242a932cefa794d81db56e59a9c787433695f8c12c39e8500a09141d4a155c |
| g3-s1216-p55873-send.bin | a49231917dd16a7a08c0bbf2e09adf23464740c91a1379e22befa08c7710da64 |
| g3-s1216-p55873-recv.bin | 6bd0d76200a1e893f2604866b0c7d611f868494eb9b0df9eead2010b31108c51 |
| startup-analysis.json | 703bd85547221e85fb9ad55462cb193d6240a8197f3cad10c4eee119071c7ef6 |
| application-records.json | 89b5a12ed9954230b892f10a0a5d21f5be5fbc3c751306e8f0393656c749cd14 |
| image-actions.jsonl | a036d15e2d6ec077d35a8788a3f43b84e7af30a0f2c6a591a626ac547a4b6354 |

## Fedora next stage

Use the prepared private transfer bundle and its import instructions. Verify hashes before merging, retain a durable private copy outside the existing repository, and preserve that repository's history and edits. Carry all four Windows run directories and the Fedora static evidence forward; no Windows node_modules or native tool installation is needed on Fedora merely to read evidence.

Reproduce the observed record parsing offline. Inspect the few startup routines to identify field semantics, mixed-endian fields and validation/error behavior. Keep facts separate from hypotheses; avoid treating one successful exchange as a universal handshake. No further Windows cable action is required for this transfer's planned capture work.
