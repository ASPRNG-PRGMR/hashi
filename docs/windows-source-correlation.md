# WIN-NEXT-01: controlled image correspondence

Updated 2026-11-04, Asia/Calcutta. Event times below are UTC. Read together with [Windows return investigation](windows-return-investigation.md), which retains the November 3 socket-return proof, verified artifacts and unsuccessful image controls.

## Outcome

**Fact:** On November 4, twelve selected successful agent send buffers from the Apple-loopback socket decoded as 1280×960 JPEGs. Their sampled square pixels followed the controlled white → black → white sequence, with the expected gray background. Six independent local screen-pixel checks established that the intended pattern was actually present. Early and late samples in each phase agreed.

**Fact:** On November 3, usbmuxd_connect returned the observed Apple-loopback socket and the agent used it at the same direct Winsock send call site, RVA 0x2f718. That observation belongs to the earlier process/connection. Today's attachment began after connection establishment and does not claim a second observed usbmux return.

**Inference:** The matching-build socket-return proof plus this controlled content match establish the intended transport conclusion: the agent's Apple-loopback path carries image-dependent session traffic through direct Winsock. WIN-NEXT-01 has now answered its focused behavior question across these two sessions. It has not established a complete interoperable protocol.

**Fact:** The user separately confirmed that the final November 3 DPI-corrected test was visible and the display worked. That confirmation is now preserved. The older identical-buffer result remains unexplained; it was not merely a missing user confirmation. Conditions changed on November 4, including a fresh agent process and stronger sampling/visibility checks. Do not assert that DPI alone, a restart, or a timing change caused the successful result.

## Current identity and runtime boundary

New private run **S**: `<private-evidence-root>/runs/source-check-20261104-142811`, outside this checkout.

**Fact:** The active workspace is unchanged. Earlier working changes and the nested older workspace were preserved. No new source protocol implementation, vendor installation modification, driver installation, or pairing change was made.

Installed binaries reverified against the November 3/Fedora artifacts:

| Artifact | SHA-256 |
| --- | --- |
| SWXDAgent.exe, x86 | cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c |
| libusbmuxd.dll, x86 | f198c3649d934fe6dc1004541d06844348009d792ea02fbb79d706ef30fdeda3 |

| Observed item | Value |
| --- | --- |
| Agent / Apple service PID | 26200 / 10072 |
| Agent / libusbmuxd / WS2_32 load base | 0x007c0000 / 0x73930000 / 0x75b60000 |
| Socket handle | 1380 (0x564) |
| Endpoint tuple | 127.0.0.1:52578 → 127.0.0.1:27015 |
| Four-byte send call / return | Agent RVA 0x2f702 / 0x2f708; runtime 0x007ef702 / 0x007ef708 |
| Payload send call / return | Agent RVA 0x2f718 / 0x2f71e; runtime 0x007ef718 / 0x007ef71e |
| Test physical monitor | DISPLAY7, bounds (1920,0),1280×960 |
| Test control | #202020 background, 160×160 square at local (100,100) |
| Helper visibility | Visible window, session 1, display-affinity query succeeded with value 0 |

**Fact:** The observer discovered live module bases and captured current imports/instructions before hooking. It checked send/recv calls to the matching Apple endpoint without the previous agent/libusbmuxd-only caller filter. WSASend and WSARecv entry/return observation was also added for this endpoint; no matching calls to those APIs were observed in this window. This bounded negative result does not establish their global absence. Overlapped completion handling was not exercised.

## Controlled image correspondence

**Method:** Reused the per-monitor-v2 helper, added local desktop pixel reads at square center (180,180) and background (400,400), and recorded window visibility, affinity, process/session and form/panel bounds. No full desktop screenshots were saved. A passing pixel check armed two JPEG-buffer samples about 750 ms later; checks occurred early and late within each ten-second phase. Samples were copied before send and retained only for the positive accepted length. Each selected call accepted its entire requested buffer. Maximum individual sample allowance was 512 KiB.

**Fact:** All six local probes matched exactly: square RGB was (255,255,255), then (0,0,0), then (255,255,255); background remained (32,32,32). The test process's logged screen bounds and client size were 1280×960 throughout.

**Fact:** All twelve buffers decoded locally using System.Drawing.Bitmap. For each image, all 49 sampled interior-square points matched the expected phase exactly. Three additional decoded background points matched #202020 within three channel levels. This is a sampled pixel check, not a whole-frame equality claim.

| Phase | Trace sample event sequences | Sample times, UTC | Each accepted buffer | Decoded square mean/min/max |
| --- | --- | --- | ---: | --- |
| White before, early | 1482,1485 | 08:59:51.099 / .132 | 26,536 bytes | 255 / 255 / 255 |
| White before, late | 1871,1874 | 08:59:56.072 / .108 | 26,536 bytes | 255 / 255 / 255 |
| Black, early | 2254,2257 | 09:00:01.013 / .022 | 26,138 bytes | 0 / 0 / 0 |
| Black, late | 2655,2658 | 09:00:06.060 / .073 | 26,138 bytes | 0 / 0 / 0 |
| White after, early | 3128,3131 | 09:00:11.022 / .040 | 26,519 bytes | 255 / 255 / 255 |
| White after, late | 3611,3614 | 09:00:16.052 / .082 | 26,519 bytes | 255 / 255 / 255 |

| Selected phase-buffer identity (four copies each) | SHA-256 |
| --- | --- |
| White before | 446cccc6918db7da285097c8eb9934bcc86c18d9846219537d29ea99d72a80db |
| Black | fdc37aba81f03ba5260beef4e5d6da16652ee182ada082d3fe29a73b7b0ae26f |
| White after | 3b6d146001ec126bf94b831d7a7eaa2b86ce638f377eb083ada0908013447a18 |

**Limitation:** White-before and white-after full-buffer hashes differ. Matching sampled square/background pixels does not mean every other pixel or compressed bit was unchanged. No general compression-quality, cursor, frame-rate, encryption, frame-boundary or codec-negotiation claim follows. JPEG is established for these accepted buffers only. TCP sends, stream messages, USB transfers and frames remain distinct.

## Coverage and cleanup

**Fact:** The trace recorded 5,637 consecutive events without sequence gaps or script errors. There were 5,616 completed direct sends: 2,808 at each of the two observed return RVAs. No matching recv, WSASend or WSARecv completions/calls were observed. Accepted send bytes across the whole attachment totaled 219,332,690; this includes time outside the controlled test. No negative or partial completed send returns were recorded.

**Fact:** Hooks were removed, the script unloaded and attachment detached at 09:00:38.403Z. No pending recorded calls or cleanup errors remained. The final sequential baseline at 14:31:23.637–14:31:28.234 +05:30 retained the agent, Apple/iPad/XDISPLAY devices and connection. This machine-state check is distinct from user visual confirmation; no new November 4 post-test visual confirmation was solicited.

**Fact:** No Ghidra reinstall was performed for this run. Runtime evidence here comes from Frida 17.23.2 Node bindings and local checks rather than from static analysis.

## Evidence and next step

S\evidence-index.json maps all 40 verified records to these locally assigned IDs:

| ID | Contents |
| --- | --- |
| WIN-SOURCE-E001 | Prior final user confirmation, current baselines/identities and actual tool-availability record |
| WIN-SOURCE-E002 | Trace, local pixel/action log and authored observer/helper scripts |
| WIN-SOURCE-E003 | Twelve private JPEG buffers, decoder and decoded pixel results |
| WIN-SOURCE-E004 | Source-correlation analysis script and complete result |

| Evidence file | SHA-256 |
| --- | --- |
| evidence-index.json | 07965d6ab45c0019eb7a63aabbcaedbb228fecbfb772c9a0f1166d81d337d2a0 |
| trace.jsonl | cb9cec9f08cc26009e44d67f2acdc50411feefb83b6d9ba0491d07d5d2c5db27 |
| image-actions.jsonl | 2c51df35ed0376e42afa8ff195e125a7c36ffff5b2953c86347e33eba0cbf128 |
| source-correlation.json | 4e8580e10393f1ca18bb45199e00dca8b48944992940a8cee1dacebc527560d7 |

The focused transport/image question is answered for the observed build and configuration. Preserve the failed controls and both run roots when transferring evidence.

**Next experiment, WIN-NEXT-02:** Establish the application startup exchange and framing at the now-proven boundary. Start from the existing November 3 connect trace and narrow static callers; identify which startup bytes are fully retained versus truncated prefixes. A new bounded reconnect capture may be needed to preserve complete successful bidirectional stream bytes. Reassemble by connection generation and direction, handle partial I/O, and correlate the observed port argument 6789 without assuming it is universal. Validate any candidate four-byte length/type interpretation against multiple actual buffers and instructions. Do not implement a guessed protocol, equate send calls with messages, or generalize these JPEG samples to every mode.
