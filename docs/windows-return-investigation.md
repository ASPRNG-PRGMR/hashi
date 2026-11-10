# Windows return investigation — WIN-NEXT-01

## Subsequent result — 2026-11-04

[Windows source correlation](windows-source-correlation.md) records the successful continuation: six independent screen-pixel checks and twelve decoded JPEG buffers matched white → black → white. This supplies the image-dependent-content evidence missing from the November 3 runs below. Today's already-connected socket was in a fresh process; the original usbmux return proof remains a separate earlier observation of the matching build/call path.

The user also confirmed that the final November 3 DPI-corrected test was visible and the display worked. Its six identical captured images remain unexplained. Preserve that negative result; do not claim that DPI alone caused or fixed it. The historical findings and hashes below are unchanged.

Updated 2026-11-03 (Asia/Calcutta). Evidence timestamps below are UTC unless a zone is shown. This report supplements RETURN-TO-WINDOWS.md and supersedes older setup/path and transport-unknown statements where explicitly supported below.

## Result and boundary

- **Fact:** The observed x86 usbmuxd_connect call returned socket 1352 (0x548) to SWXDAgent RVA 0x30ca1. Its endpoints were 127.0.0.1:62541 → 127.0.0.1:27015. The device-handle argument was 2 and the port argument was 6789 (0x1a85). These are observations of this connection, not universal constants.
- **Fact:** The same socket, tracked within the reconnect trace as generation 3, reached the agent check routine through ECX and carried successful direct Winsock sends at the predicted call RVAs 0x2f702 and 0x2f718. The first requested/accepted four-byte and sixteen-byte sends also executed at RVAs 0x30476 and 0x30590.
- **Fact:** Later bounded attachments observed the same PID, socket number and endpoint tuple. Twelve selected successful payload-send buffers decoded locally as 1280×960 JPEG images. Thus this boundary carries image content; it is not solely short setup/control exchange.
- **Inference:** These observations support the Apple loopback stream as a display-session transport. The later attachments do not continuously prove socket lifetime across their detach gaps.
- **Fact / unresolved:** The final six buffers were byte-identical across the helper's logged white/black/white changes and did not match the expected test-square pixels. A corrected DPI placement did not resolve that discrepancy. Controlled causal image dependence remains unestablished; do not describe WIN-NEXT-01 as wholly completed.
- **Fact:** No speculative protocol or Linux implementation was added. All instrumentation detached; no driver, pairing or vendor installation change was made.

## Workspace, preservation and verification

**Fact:** The active directory is a Git checkout that was clean at inspection. The earlier extracted `hashi-main` path did not exist. The older workspace remains under hashi-stuff\hashi-main and was preserved. No remote was added and no Git commit/staging operation was performed.

Private run **R**: `<private-evidence-root>/runs/return-20261103-232442`, outside this checkout.

Private imported Fedora bundle **F**: `<private-evidence-root>/return-20261101/FEDORA-private-20261101`, outside this checkout.

**Fact:** The prior extraction checked ZIP members for absolute/traversing paths, duplicate names, link/special types and expanded-size bounds before extracting 37 files (10,499,378 bytes) into a new private directory. The nested archive hash was verified before extraction. This continuation independently reverified its hash, all 30 records in the Fedora evidence index, and all 32,279 original transfer-manifest files (751,064,767 bytes), with zero mismatches/missing entries. The original manifest root is the active checkout's hashi-stuff directory; newly added packaging files are outside that manifest's scope. See WIN-RETURN-E001.

| Artifact | SHA-256 |
| --- | --- |
| Outer transfer archive (identity recorded; no earlier trusted outer digest supplied) | ac8a0c3f53f332a7f3b356ee1bc79bb382d1e371aed4b3836ff9776457ba69d0 |
| FEDORA-private-20261101.zip | 900a096b2efd0b29667790bc35b28d6fce1ba9c936189b273205e45c912ba9f2 |
| Fedora evidence-index.json | f15b920830bf53b3376d574fbe94dddcd9718fc45eb353539e2a9d837ca33013 |
| Fedora transfer-manifest.json | 9d6d480efb71d1c06dad0d7e8c479eccff73a8d819fbb31164b05324c6ae650c |
| Installed and restored SWXDAgent.exe | cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c |
| Installed and restored libusbmuxd.dll | f198c3649d934fe6dc1004541d06844348009d792ea02fbb79d706ef30fdeda3 |
| Transferred study-build\ex06_hashi.dll | 6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786 |
| Original analysis\study-mcp-evidence.json | ad3db4603717f09be1aa72d6828c70659906b8aa8d2e5a697a323c56d44b4e67 |
| R\verification.json | d64f2fbf8affa364327291a4033ea5f94af0c42ba6fd097221297d813142e964 |

**Fact:** R\windows-path-mapping.json maps historical Fedora analysis paths to F\analysis, and the historical staged Windows run to the private\runs\20261031-184820. Historical Linux paths inside raw artifacts remain unchanged. Its SHA-256 is 4732cfe66c8f31a553758cbe71f9458685c483a14ad16c7a78dc502c9f9aa33d (WIN-RETURN-E008).

## Tools actually available

**Fact:** Reused the existing Ghidra 12.1.2 and JDK 21.0.12 installations from the private tool root. The reviewed-shell checks passed; the restricted-shell native self-test failed with access denied, and reinstalling Java was not indicated. No study rebuild was performed.

**Fact:** No interactive disassembly session was available during this run, so no fresh static analysis was performed. The November 1 study-analysis evidence is preserved and hash-verified; it is historical evidence, not a fresh check. See WIN-RETURN-E003.

**Fact:** The missing native binding for the already-transferred Frida 17.23.2 package was installed from its versioned official GitHub release using the package's prebuild installer. Native binding SHA-256: 32c73230bdfd4b9a8f1f1871ef616001e486269919f18a111a195854352057dc. Runtime observations below used the Node bindings directly. WIN-RETURN IDs are locally assigned investigation identifiers.

An earlier continuation was stopped by automatic approval review's workspace spending-cap failure, before its command executed. Reviewed execution succeeded on this continuation. No approval restriction was disabled or bypassed.

## Reconnect, addresses and lifetime

**Fact:** Initial agent PID 26580 and Apple-service PID 9976 were observed with agent source port 60066. After the user replied “disconnected,” the disconnected baseline lacked the Apple/iPad/XDISPLAY device entries and agent Apple connection. Both principal processes persisted. The trace was ready at 17:59:25.760Z, before reconnect. The user then replied “connected” when asked to report the extended display's return. Exact physical cable action times were not measured.

| Module / boundary | Observed runtime address or mapping |
| --- | --- |
| SWXDAgent.exe base | 0x00cc0000 |
| libusbmuxd.dll base | 0x73c90000 |
| WS2_32.dll base | 0x74970000 |
| Agent usbmux call / return (RVA 0x30c9c / 0x30ca1) | 0x00cf0c9c / 0x00cf0ca1 |
| DLL usbmuxd_connect export (RVA 0x2f90) | 0x73c92f90 |
| DLL Winsock connect call / observed return (RVA 0x3cd1 / 0x3cd7) | 0x73c93cd1 / 0x73c93cd7 |
| Agent check entry (RVA 0x303f0) | 0x00cf03f0 |
| Agent send IAT (RVA 0x17b99c, ordinal 19) | 0x00e3b99c → 0x749875a0, equals loaded send export |
| Agent recv IAT (RVA 0x17b9a0, ordinal 16) | 0x00e3b9a0 → 0x74986c40, equals loaded recv export |
| Agent connect IAT (RVA 0x17b9a8, ordinal 4) | 0x00e3b9a8 → 0x74987730, equals loaded connect export |
| DLL send / recv / connect IAT RVAs | 0x50ec / 0x50fc / 0x5114; resolved to the same corresponding exports |
| Ongoing agent send calls / observed return RVAs | 0x2f702 → 0x2f708; 0x2f718 → 0x2f71e |
| Agent receive helper call / observed return RVA | 0x112e8 → 0x112ee |

**Fact:** Trace events 17–25 establish the targeted connection:

- At 18:00:30.233Z, usbmux entry call ID 11, thread 2420, return address 0x00cf0ca1. Raw x86 argument stack bytes: 02 00 00 00 85 1a 00 00. Numeric device handle 2; port argument 6789, not local Apple port 27015.
- Nested Winsock connect returned 0 on socket 1352; endpoint tuple 127.0.0.1:62541 → 127.0.0.1:27015. The captured sockaddr identifies AF_INET and network-order local-service port bytes 69 87.
- At 18:00:30.238Z, usbmux returned EAX 0x548 (1352); its observed return address matches agent RVA 0x30ca1. The subsequent check at RVA 0x303f0 received ECX 1352 and the same tuple.
- Handle 1352 had already been used for a different earlier connection with source port 62540. The trace observed closes and assigns connection generations; numeric socket equality alone would have conflated generations 2 and 3. Generation 3 was the returned session socket.

Direct send/recv hooks paired entry and return through invocation-local state and thread IDs. Send prefixes were copied before the call and truncated to positive accepted lengths; receive prefixes were read after success. Error/partial-I/O fields were retained. Only calls returning into the selected agent or libusbmuxd module were logged. Loaded IAT targets were checked against loaded Winsock exports; the trace did not rely on preferred-image VAs.

## Image trials, correction and limitation

**Fact:** Each helper run logged two seconds of settling, ten seconds white, ten seconds black, and ten seconds white; only a nominal 160×160 region at (100,100) changed on a #202020 background. The first trial was missed by the user. The user explicitly requested a repeat and then confirmed “Saw both changes; display works.” This report applies to repeat-02, not automatically to later trials. A separate visual confirmation was requested for the final corrected trial.

| Run | Trace events | Completed I/O records | Accepted send bytes over entire attachment | Cleanup |
| --- | ---: | ---: | ---: | --- |
| reconnect-01 | 7,937 | 7,923 | 394,428,834 | Hooks removed, unloaded, detached |
| repeat-02 | 5,703 | 5,700 | 294,032,139 | Hooks removed, unloaded, detached |
| content-03 | 5,404 | 5,392 | 235,403,035 | Hooks removed, unloaded, detached |
| content-04-dpi | 4,394 | 4,382 | 192,803,618 | Hooks removed, unloaded, detached |

**Fact:** No sequence gaps, script errors, negative/partial completed I/O returns, pending recorded calls at stop, or cleanup errors were recorded. These are API-byte totals over each whole attachment, not wire-byte totals, frame counts, or only controlled-phase totals. No packet capture was taken; absence of receive completions in later runs does not exclude unhooked receive APIs or traffic outside scope. The candidate receive call at RVA 0x2f921 was not established as executed by this capture.

**Fact:** Initial size comparisons were not a clean image-dependence result. For example, the first white-to-black action at 18:01:07.902Z was followed by a change from 24,086-byte payload sends to 23,304-byte sends; later nominally static intervals also showed large unrelated variation. R\trace-analysis.json preserves full phase counts, one-second bins, local transition windows and limitations rather than hiding that variation.

**Fact:** The initial helper used a system-DPI context and reported secondary bounds (2400,0),1600×1200. A per-monitor-v2 thread-context probe returned physical bounds (1920,0),1280×960, consistent with the decoded image dimensions. The corrected content-04-dpi helper used those physical bounds, disabled WinForms autoscaling, and recorded a 1280×960 client area. Only the helper's DPI context was changed; Windows display configuration was not changed. Microsoft's [DPI context documentation](https://learn.microsoft.com/windows/win32/hidpi/dpi-awareness-context) explains why system-aware and per-monitor-aware window coordinates/scaling differ. **Inference:** DPI handling confounded the earlier placement; it does not explain away the final negative match.

**Fact:** content-03 and content-04-dpi each sampled two complete successful send buffers per phase, at most 512 KiB per sample, copied on entry and retained only after a positive return. All twelve begin/end with JPEG markers and decode via Windows System.Drawing.Bitmap as 1280×960 JPEGs. Their raw bytes remain private. This establishes JPEG content for these samples, not the complete stream's framing, all supported codecs/modes, or one-frame-per-send semantics.

**Fact:** All six corrected-run buffers are exactly 87,994 bytes, SHA-256 85993181fcaa5393abb353a094a950b4a29eedd634168f0018ac7788253541bf. Their 49 sampled interior square positions have mean RGB-channel intensity approximately 51.88, not the expected white 255 / black 0. The preceding content-03 samples also failed the expected-position test. Therefore the nominal control did not establish a reversible square-content match. Preserve this negative result.

**Hypotheses, not conclusions:** The helper's visible window/session/desktop or capture selection may differ from the actual image source; stale or alternate image content may be involved. Neither a frozen display, a second protocol, nor driver failure is established. The next observation must independently establish actual window placement/visibility and compare the controlled image with the decoded buffer, rather than accumulating more traffic-rate traces.

## Evidence map and hashes

All paths below are relative to R. The private evidence-index.json enumerates individual file hashes for these local IDs. Preserve the index and its digest alongside any private transfer.

| ID | Principal contents |
| --- | --- |
| WIN-RETURN-E001 | verification.json, original manifest/index and artifact verification |
| WIN-RETURN-E002 | Current/disconnected/post-repeat/final baselines and user cable replies |
| WIN-RETURN-E003 | toolchain-doctor.json, tool-availability.json, Frida installation log |
| WIN-RETURN-E004 | First trace, hooks/runner, test helper and action log |
| WIN-RETURN-E005 | repeat-02 and user-repeat-confirmed.json |
| WIN-RETURN-E006 | Analyze-Trace.mjs and trace-analysis.json |
| WIN-RETURN-E007 | Both bounded content runs, samples, pixel checks and Decode-TestSamples.ps1 |
| WIN-RETURN-E008 | windows-path-mapping.json |
| WIN-RETURN-E009 | Summarize-Runs.mjs and final-run-summary.json |

| Evidence file | SHA-256 |
| --- | --- |
| trace.jsonl | c0642047683ee41a0de962926fb6eac195f8b31cbe0303c82df560515641a67a |
| repeat-02/trace.jsonl | 6a36f0046ec78b26d0d04f3f2512b405c097bb1caee60d6746374613919d636a |
| content-03/trace.jsonl | 2346b3336bb258a85e1d4de628fb19368748ad87fe6e772fea339cd4c68f3c3c |
| content-04-dpi/trace.jsonl | 95637e9f7687cb2985405f7203a64fa120007a46e42f0c27e20e6b998dab8822 |
| content-04-dpi/image-actions.jsonl | 1f4644dc7542e4a30a9f17740ae0740a5578d4c4cb21414f0d96ce8d418132ee |
| final-run-summary.json | 5f915c6109062d270a1235e11dca2ce75aba6d53d0bf1f0a6a9c0c2d3f851c4e |
| toolchain-doctor.json | 0daf4e36a1bc8ea9e7f81b838f4e5361911ddbaad7773b26f27adfb3ae097e5f |
| tool-availability.json | 2d121a85043e2ce5a5fcb3f33560c2295c05e8533e1993c66306f4fc7afa3e66 |

## Next discriminating observation

1. Read this report and the latest RETURN-TO-WINDOWS.md update before older plans. Verify R's index and sampled-buffer hashes. Keep raw payloads private.
2. Confirm current display operation and whether the final corrected pattern was actually seen. Do not carry the repeat-02 user confirmation forward as confirmation of another run.
3. Inspect current session/desktop, per-monitor DPI context, physical monitor and actual window bounds/visibility. Use a known test window on the verified image source. Independently verify its appearance before another buffer experiment. If it is not visible, fix that test-control issue first without changing the working driver setup.
4. Reuse the bounded content observer with new filenames. Compare decoded images against an unmistakable controlled region (position may need a measured coordinate transform). Require repeatable white/black/white content correspondence before claiming causal image dependence. Record failures as evidence. Reconnect only if a fresh handle-lifetime proof is needed.
6. Only after the image source is established, investigate the startup handshake and adjacent four-byte records using successful stream bytes. Do not assume those records are a validated length/type header. No speculative protocol implementation is authorized by these observations.
