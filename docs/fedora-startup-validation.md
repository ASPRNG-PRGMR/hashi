# Fedora startup validation — 2026-11-05

## November 6 static continuation — FED-BACKEND-E001 / FED-FRAME-E001

**Fact (FED-BACKEND-E001, 2026-11-06):** The checkout was clean on `main` at `12d6499` before this continuation. The agent remains SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`. Independent objdump of `CConnectBase::InitCaptor` at RVA `0x2f300` verifies the five-rung priority ladder. In order, its config gates, availability helpers, constructor RVAs and resulting class vtables are: `( +0x44=0, +0x60!=0, 0x35ac0, 0x35570, 0x1ac4b4 Lci )`; `( +0x44=0, +0x5c!=0, +0x50 passed via ESI, 0x378f0, 0x37270, 0x1ac678 OSBase )`; `( +0x58!=0, 0x34280, 0x33e80, 0x1abeb0 FBCToSys )`; `( +0x54!=0, 0x334f0, 0x33200, 0x1ab9a8 Dxgi )`; then unconditional `( 0x37f10, 0x1ac7ac StVD )`. Allocations are `0x1c4`, `0x250`, `0x1ac`, `0x1ac`, `0x1a0`. The stores of 0–4 at `0x2f350`, `0x2f3a2`, `0x2f3eb`, `0x2f42c`, `0x2f459` are exception cleanup state, **not persistent captor-type indices**. If the selected object's virtual slot `+0x10` initialization fails, `0x2f4b1`–`0x2f4f5` destroys it and constructs OSBase as fallback. The previous unrecorded interpretation of those integers as type indices was wrong.

**Fact (FED-BACKEND-E001):** Constructor vtable stores and PE RTTI complete-object locators agree on the five class names above. The two thread vtables are `0x1ac4a8` → `CCapThreadLciProxy` → method RVAs `[0x34ef0, 0x43f0]`, and `0x1ac66c` → `CCapThreadOSBase` → `[0x36d40, 0x43f0]`. The capture class vtables each have eight established slots: Lci `[0x33270,0x19ba0,0x19bf0,0x35820,0x35d60,0x36410,0x251b0,0x36600]`; OSBase `[0x372d0,0x19ba0,0x19bf0,0x37630,0x37950,0x37bb0,0x36d30,0x37ce0]`; FBCToSys `[0x33270,0x19ba0,0x19bf0,0x33f30,0x34530,0x34740,0x33e70,0x34850]`; Dxgi `[0x33270,0x19ba0,0x19bf0,0x332a0,0x33620,0x33940,0x331f0,0x33a90]`; StVD `[0x33270,0x19ba0,0x19bf0,0x37f70,0x381c0,0x383c0,0x24d60,0x384d0]`. All are module-relative RVAs from preferred base `0x400000`. A live vtable needs subtraction of the live module base before matching. The names of the two driver-check classes exist in RTTI, but their functions and the persisted config source are **not yet resolved**.

**Fact (FED-FRAME-E001, 2026-11-06):** An offline pass over all 1,903 tag-6 records in WIN-START-E005 found 39 distinct payload hashes, 12 duplicate-hash groups, and a largest group of 1,044 records. Payload size min/median/mean/max is 19,827 / 26,568 / 68,506.31 / 369,050 bytes. Every frame has the same ordered DQT/DHT segment hashes and SOF0 component sampling bytes `(0x22,0x11,0x11)`, i.e. 4:2:0. Mapping each record start offset to the containing accepted `trace.jsonl` send chunk gives inter-frame start intervals min/median/mean/p95/max of 2 / 19 / 20.37 / 31 / 51 ms, from epoch milliseconds `1793855479482` to `1793855518233`. Chunk start times have millisecond precision; these are recorded send-start intervals, not display refresh times. **Inference:** constant tables are consistent with fixed-quality ordinary JPEG; they do not distinguish ordinary from differential JPEG, because the latter could also emit the same tables. The class selection remains a runtime question.

**Fact (FED-FRAME-E001):** `hashi_framing.py` implements only tag + unsigned BE24 length + payload parsing and SOI/EOI/SOF0 boundary inspection. Three synthetic tests pass; no capture bytes or guessed messages are in the repository. Private measurement scripts and results are in `D/analysis/fedora-backend-20261106` (mode 0700, files 0600). No Windows binary was run or protocol message sent on Fedora. The user declined active iPad replay on November 6.

**Fact (FED-BACKEND-E001):** All 12 preserved `modules.json` snapshots across the four Windows runs omit `kernel32`, `user32`, `gdiplus`, `d3d11` and `dxgi`. They were filtered to non-system paths. **Inference:** Absence of DXGI in those snapshots cannot identify the capture backend; the next observation needs a full module list.

**Unresolved:** Config field writes/source, precise availability-helper semantics, complete probe calling conventions and runner, and phase-separated frame statistics still need static/offline work. Windows still must supply the live captor vtable, shared-state values, complete loaded-module list, display modes and selected monitor rectangle, and calling-thread DPI context.

**Fact:** The November 5 Windows capture reproduces offline on Fedora: 1,903 JPEG records, exact application-stream consumption, and twelve decoded samples matching the controlled square. The source import is committed as `c63c354`. No protocol messages were transmitted or implemented. This report supplements [Windows startup/framing](windows-startup-framing.md); its observations govern the older Fedora plans.

**Continuation, November 5:** The actual Codex REA MCP study check now passes with the unchanged DLL. Client dimensions and encoder dimensions are distinct fields. The LCI sizing helper maps 2048×1536 to an initial 1600×1200 request, but subsequent monitor refresh overwrites the encoder dimensions with the selected monitor's size. The captured Windows monitor and JPEGs are both 1280×960. The exact runtime backend and reason Windows/the driver selected that mode remain unobserved; no fixed 2048→1280 scaling rule is established. See FED-REA-E001 and FED-SIZE-E001–E003 below; these supersede the live-connection blocker and downstream-analysis TODO in the original report.

## Preservation and reconciliation — FED-IMPORT-E001

**Fact:** The authoritative repository was clean on `main` at `9d7771d9e74df77a4e9666f759af5eeb6d68546c`. Its existing history, branch and `origin` were retained. All nine declared paths in `changes.json` were reconciled against the supplied base snapshot and actual Git base. Each existing local file equaled that base, so no conflicting three-way merge was needed. The supplied patch passed `git apply --check`; only declared source files were imported. Four new Markdown files had one terminal CRLF normalized after the whitespace check detected it. Original source bytes remain preserved.

Durable private root, **D**:

```text
/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z
```

**Fact:** `D/bundle` preserves the complete original transfer: 1,991 indexed files totaling 267,453,281 bytes, plus both manifest files (1,993 files in total), and both empty directories. Every file's path, size and SHA-256 was checked; links, special files, traversal and unaccounted files were rejected. Copy verification also compared the otherwise unindexed manifests and complete directory inventory. Private directories are mode 0700 and files 0600. No inbound ZIP was used or supplied at the requested path; no claim is made about an unavailable archive's identity.

| Identity / index | SHA-256 / verified records |
| --- | --- |
| Bundle `manifest.json` | `5545e52d07cb4d8bfd0368795f11da411d5af59e47d019c03f434775583bbbff` |
| Fedora November 1 index | `f15b920830bf53b3376d574fbe94dddcd9718fc45eb353539e2a9d837ca33013`; 30 records |
| Windows return index | `6e329ea0038efe935aaada23798ef46ff360006ea8571cec0455b799a878fd9d`; 72 records |
| Windows source-check index | `07965d6ab45c0019eb7a63aabbcaedbb228fecbfb772c9a0f1166d81d337d2a0`; 40 records |
| Windows startup index | `dc5eff1ce1cc610a44ecc33d6f1c290a82551f30e5a73defa10f16bf2b63af52`; 49 records |

**Fact:** All 191 records in the four supplied evidence indexes verified in their mapped roots. The October 31 run has no separate `evidence-index.json` in this bundle and is covered by the bundle inventory. The historical 32,279-file transfer manifest describes an older tree and was retained as provenance, not used as this bundle's inventory.

Mappings are recorded in `D/preservation-receipt.json`: historical Windows `HASHI-private/runs/<run>` maps to `D/bundle/private-evidence/windows-runs/<run>`. Historical `/tmp/HASHI-private-fedora-20261101-9i_xb6aj/analysis` maps to `D/bundle/private-evidence/fedora-20261101/analysis`. Paths within raw evidence were not rewritten. Earlier failed image controls, original timestamps, study artifacts, source/base snapshots, patch and instructions remain intact. `D/hashi-initial-verification.json` inventories every original file; `D/analysis/index-reconciliation.json` records the index and source comparisons. Private receipts, captures, binaries and raw analysis are excluded from Git.

## Offline reproduction — FED-START-E001

**Fact:** Independent Python parsing checked 11,495 consecutive trace events, 3,827 complete successful I/O chunks, contiguous offsets in six direction files and 130,378,071 accepted bytes. Recorded overlap, copy errors, partial/failed I/O, capture-limit events and script errors were absent. These checks describe the recorded APIs and time window, not all possible traffic.

The application offsets were derived from the first post-return agent chunks on the returned generation-3 socket, including its endpoint tuple. They reproduce outgoing offset 592 and incoming offset 294. The parser uses the observed tag byte and unsigned BE24 length; truncated-header and truncated-payload checks also passed.

| Direction | Application bytes | Records | Result |
| --- | ---: | ---: | --- |
| Host → iPad | 130,375,177 | 1,907: tag 4 × 1, tag 5 × 3, tag 6 × 1,903 | Exact end; no tail |
| iPad → host | 52 | 4: tag 4 × 1, tag 5 × 3 | Exact end; no tail |

**Fact:** Every parsed record's offset, tag, length and payload hash equals the supplied ledger. All 1,903 tag-6 payloads have JPEG SOI/EOI and SOF0 declaring 8-bit, three-component 1280×960 images. Pillow 12.3.0 fully decoded the twelve selected samples. All 49 interior-square points per image matched the expected white/black/white phase exactly; all three background probes were within three channel levels of 32. Samples equal the corresponding accepted stream slices byte-for-byte. This does not establish whole-image identity or other codec modes.

**Fact:** The supplied `Analyze-Startup.mjs` and `Parse-ApplicationRecords.mjs` were replayed in a separate private working directory. Both generated JSON documents equal the originals except their fresh top-level `utc`; all twelve extracted files are byte-identical. `D/analysis/validate_offline.py`, `offline-validation.json` and `replay/` retain the independent checks and replay. The bundle originals were not modified. Original event times, including the 05:11:18.383Z connect return and sampled frame timestamps, remain in those results.

## Focused startup-field analysis — FED-START-E002

**Fact:** Analysis used GNU objdump 2.46.1-1.fc44 and independent PE import/string inspection, on the x86 agent SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c` (recorded product/file versions 1.5.8.3 / 1.58.9.6924). All locations below are **module-relative RVAs**, with static preferred base `0x400000`; they are not live Fedora execution addresses. Raw instructions and selected strings remain private under `D/analysis`.

1. **Fact:** The routine at RVA `0x303f0` references the diagnostic label `CProbeUsbmuxd::DoHandshake`. A tag-4 reply selects a flag at RVA `0x304d2`–`0x304f7`. That flag controls conversion through Winsock import slots at RVAs `0x17b988` (ordinal 8) and `0x17b994` (ordinal 14), versus direct native-order field handling. The observed outgoing subtype 1 and incoming subtype 2 follow this converted branch. **Inference:** The tag-4 exchange selects the observed network-order representation; the alternate branch remains unobserved and must not be implemented from this slice alone.

2. **Fact:** The first tag-5 response's payload word at offset 0 is converted and compared with 2 at RVAs `0x305dd`–`0x305f9`. Payload offsets 4 and 8 are conditionally converted at `0x30655`–`0x3067c`, producing 2048 and 1536 for the captured bytes. After accepting subtype `0xff`, the values are rounded upward to multiples of four and stored at connection-object offsets `+0x14` and `+0x18` (`0x30783`–`0x3079b`); the byte-order flag goes to `+0x40`. A nearby diagnostic calls these values client resolution. **Inference:** These are client-reported dimensions, with stronger support than numerical resemblance alone. Their relationship to the transmitted 1280×960 JPEG size still requires downstream data-flow analysis.

3. **Fact:** The next outgoing subtype `0xfc` is conditionally converted at `0x30802`–`0x3081f`. Its following word is stored directly as integer 5 at `0x30829`, before send at `0x30831`, yielding captured bytes `05 00 00 00`. **Inference:** This field is a native little-endian 32-bit constant in this build, not BE32 value 83,886,080. Its meaning is still unknown. It must not be called a codec/version selection merely because it equals 5.

4. **Fact:** Before this later exchange, RVA `0x307d1` has already set the routine's success byte. A call at `0x307d6` to helper RVA `0x2cda0` gates the exchange by comparing its result with 5. That helper resolves `ntdll.dll!RtlGetVersion`; its inspected branch returns 5 for a combined version value at least `0x0a00`. The outgoing field is separately hardcoded, not copied from the helper result. **Inference:** The extension is OS-gated, but the on-wire 5's semantic identity is not established by that gate.

5. **Fact:** Later response handling requests four header bytes at `0x3085e`, then the decoded positive payload length at `0x308ea`. It can accumulate additional body bytes at `0x30916`. These sites explain the captured 4+12 recv split without treating calls as messages. By contrast, the first two tag-5 replies require a single helper return of 16 (`0x305d4`, `0x30729`); helper RVA `0x112d0` itself makes one recv after readiness checking. **Inference:** The vendor's early reply handling may reject a short read. This was not exercised by the successful capture and is not a rule a future stream parser should copy.

6. **Fact:** The later body is NUL-terminated and passed to helper RVA `0x5c40` at `0x30966`; that helper scans to the first NUL. The captured body begins `00 00 00 fd`, so this scan yields length zero. The caller tests its string-length field at `0x309a0` before the later parse/key path containing `diff_jpeg`. No comparison accepting subtype `0xfd` appears in this inspected path. Many late error exits return the already-set success byte at `0x30b7e`. **Inference:** This captured reply follows an empty-string path and does not demonstrate successful capability parsing or negotiation of `diff_jpeg`. This is static reconstruction consistent with captured bytes, not a branch-level runtime trace.

**Limitations:** This is a bounded instruction/data-flow inspection, not whole-program decompilation or a complete error-state model. The alternate representation, other platforms/modes, startup necessity, capability semantics and downstream codec selection remain open. No guessed messages or vendor code were added to HASHI.

## Linux tools and original live-check blocker — FED-START-E003

**Fact:** Reused the full Temurin JDK 21.0.10 at `/opt/st/STM32CubeMX/jre`. The existing default Node 24.20.0 did not satisfy the pinned REA package. Installed Linux Node 24.22.1, Ghidra 12.1.4 and REA 6.8.0 under `/home/noobiegg/HASHI-private/tools/fedora-20261105`. Node and Ghidra archive SHA-256 values were checked against their official distribution metadata; npm records pinned package integrity. Package installation scripts were disabled. No transferred Windows native tools were executed and the study DLL was not rebuilt.

**Fact:** Scoped `rea doctor --provider ghidra --json` passes Node, Linux architecture, Ghidra version/headless entry, ELF x86-64 decompiler identity and full JDK checks. Unselected optional engines are not required. Codex-only setup was previewed; its single planned action preserves unrelated configuration. The registered launcher is pinned to the absolute supported Node binary so a desktop PATH cannot silently select the older Node. The original config is retained privately in D. See `D/analysis/rea-registration-receipt.json` for the applied registration and checks.

**Historical limitation, resolved by FED-REA-E001 below:** The import session exposed no REA `binary_session`, `open_binary` or `analyze_function` tools. CLI doctor was not a connected-client study check. The prescribed follow-up was to inspect the actual advertised tools and analyze the preserved study DLL, SHA-256 `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`, without rebuilding. The inherited incorrect `void` tick signature required checking against its preserved EAX return.

## Original continuation scope

Trace readers of the same connection object's `+0x14`, `+0x18`, `+0x40` and `+0x68` fields to the capture/resize/encoder selection path. Determine how client-reported 2048×1536 becomes the observed 1280×960 JPEG stream, and whether the `diff_jpeg` state can change that selection. Use focused references and bounded functions; retain the alternate mode as unobserved. Keep the working Windows installation for a specific follow-up experiment only if this analysis leaves a concrete behavioral question. No additional Windows cable cycle is needed for this import.

Cleanup is conditional on the final unchanged-bundle and committed-source checks. `D/completion-receipt.json` records the actual result and commit IDs after those gates; no cleanup claim is inferred from this pre-cleanup document.

## Actual connected-client study check — FED-REA-E001

**Fact:** The reconnected tool catalog exposes the actual REA MCP tools. `binary_session(expected_package_version="6.8.0")` reports `codex-mcp-client` 0.166.0, negotiated protocol `2025-06-18`, REA 6.8.0 and alignment `aligned`. The server command is the previously registered private installation. The tool catalog digest is `a98940ba69acd9c1781d180cee362d4ddab18f77eefdd3e3216f10e1bf98e5e9`. These are live client/server observations, not standalone CLI results.

**Fact:** Shell SHA-256 and `open_binary(provider_id="ghidra")` independently identify the original DLL at `D/bundle/private-evidence/windows-runs/20261031-184820/study-build/ex06_hashi.dll` as `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. Ghidra 12.1.4 completed analysis and returned `hashi_add` at `0x180001000` and `hashi_tick` at `0x180001050`. Both returned addresses were passed to `analyze_function`; complete dossiers were exported before closing the session. Nothing was rebuilt or executed.

**Fact:** `hashi_add` adds ECX and EDX, includes a signed-overflow check/helper call, and returns the saved sum in EAX. `hashi_tick` calls the imported `GetTickCount` through slot `0x1800b62f0`; the following NOP, stack adjustment, POP RBP and RET do not overwrite EAX. Ghidra still produces `void` pseudocode and a value-flow graph without a return value. **Inference supported by source and instructions:** the source's `DWORD` return is preserved; the recovered `void` signature is wrong. It was retained as evidence rather than silently corrected or treated as authoritative. Study dossier IDs include `ev_5c7671ebd167a792812b1fa3a935780dea8bd3814c307f7742497b66251e0c95` and `ev_3b1abca7c74c8e1f1edf6277d6b6e197af968189265520edad5feb01d401b600`.

New private evidence root, **R**:

```text
D/analysis/rea-dimensions-20261105T140157Z
```

`R/study-evidence.json` retains seven REA records; `R/agent-evidence.json` retains 47. Session identity receipts, independent RTTI checks, bounded objdump extracts, the instruction search index and integrity checks are also private. Final `binary_session` reports `open=false`, `cleanup_pending=false`. No connection reconfiguration was needed.

## Shared state and encoder selection — FED-SIZE-E001

**Fact:** Vendor analysis used the unchanged x86 agent SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`, Ghidra 12.1.4 and independent GNU objdump 2.46.1-1.fc44. Vendor addresses below are **RVAs**, subtracting preferred base `0x400000` from private tool VAs.

The connection's `+0x1c` pointer and the capture object's `+0x88` pointer refer to the shared state passed into capture construction. They are not the dimension fields themselves. `CConnectBase::InitCaptor` (RVA `0x2f300`) passes that state to the selected capture constructor. The instructions and constructors were checked to distinguish those object bases.

| Shared-state offset | Observed readers / writers | Supported interpretation |
| --- | --- | --- |
| `+0x14`, `+0x18` | Handshake stores at `0x3078c`, `0x3079b`; sizing helper callers; display setup at `0x31ea0`; rotate-event handlers | Client-reported dimensions, also mutable after startup; not necessarily encoded dimensions |
| `+0x1c`, `+0x20` | Monitor refresh and backend setup write them; encoder initialization at `0x31a1e`–`0x31a26` reads them | Current capture/encoder dimensions |
| `+0x40` | Handshake store; send loop at `0x2f647`, `0x2f6ca` | Representation flag selecting header tag/length encoding in this path |
| `+0x64` | Reset at `0x101a4`; encoder selector at `0x3195d`; event handler calls `0x31a40`, which writes it | Separate selector with priority over the differential-JPEG flag |
| `+0x68` | Reset at `0x101a7`; capability parse stores at `0x30a83`/`0x30aa8`; selector at `0x31962` | Differential-JPEG enable state in the inspected selector |

**Fact:** RVA `0x31900` selects these classes, independently verified by constructor vtables and their PE RTTI chains:

| Condition | Selected class | Initialization |
| --- | --- | --- |
| `+0x64 == 0`, `+0x68 == 0` | `CEncoderVideoJpeg` | RVA `0x3b750` |
| `+0x64 == 0`, `+0x68 != 0` | `CEncoderVideoDiffJpeg` | RVA `0x39bf0`, constructor `0x38990` |
| `+0x64 != 0` | `CEncoderVideoSRx264` | RVA `0x3c260`, constructor `0x3ba80`; also sets `+0x6c = 1` |

All three receive the shared `+0x1c/+0x20` dimensions through the initialization virtual call. A nonzero `+0x68` can change the selected encoder when `+0x64` is zero. This selector does not itself rescale those dimensions. The reset routine clears both selector fields. The previously inspected captured capability body takes the empty-string path before the `diff_jpeg` key handling; it does not demonstrate a write enabling `+0x68`. **Inference:** the capture is consistent with the ordinary JPEG default, not evidence of successful differential-JPEG negotiation. No alternate encoder was exercised.

**Fact:** The send loop at RVA `0x2f580` uses `+0x64 == 0` and nonzero `+0x40` to form the observed tag 6 and converted three-byte length. The other representation branch uses tag 2; the nonzero `+0x64` path uses tag `0x12`. These are static branches, not additional validated protocol modes. `+0x68` is not the tag selector here, so tag 6 alone cannot distinguish the two JPEG encoder classes. The separate outgoing native-order constant 5 retains its unknown meaning.

Primary dossier: `ev_a2bb14859e451307ae5f3a6f57b122cb78807047c0801dfd235400eaa9dff75e`; send-loop dossier: `ev_76d8c39ea7619d51714a4c14b622a310e58c7383ec3680b752da340c06777f35`.

## Client dimensions, sizing policy and monitor refresh — FED-SIZE-E002

**Fact:** The bounded sizing helper at RVA `0x31400` contains explicit dimension-pair rules. For input 2048×1536, the comparison at `0x314ca`–`0x314d7` reaches the stores at `0x31556`/`0x3155c`, returning **1600×1200**. The pair comparator at `0x331d0` reads the input pair passed by address; this was checked in assembly because pseudocode omits that implicit register argument. Thus this helper is not evidence of a direct 2048×1536 → 1280×960 transform. Its other branches include pair-specific substitutions, an area threshold and a ranked candidate-size helper; none is a universal 5/8 rule.

**Fact:** `CCapVideoWin32Lci::Initialize` (RVA `0x35d60`) orders the client dimensions into landscape orientation, calls that helper at `0x35f0c`, and initially stores its result into shared `+0x1c/+0x20` at `0x35f40`/`0x35f55`. Later on its successful initialization path, it calls `CCapVideoWin32Lci::UpdateMonitorInfo` at `0x36163`, **before** encoder creation at `0x363a3`.

**Fact:** `UpdateMonitorInfo` (RVA `0x35b30`) refreshes monitor enumeration and selects a monitor, with a last-monitor fallback if its lookup fails. It then calls width/height readers at `0x3cde0`/`0x3ce50` and **overwrites** shared `+0x1c/+0x20` at `0x35c4c`/`0x35c63`. Those readers select a 32-byte monitor record and return its `+0x10/+0x14` fields. The record builder at `0x3ca00`, reached from `GetMonitorInfoW`/monitor enumeration, obtains those fields as rectangle right−left and bottom−top. The initial requested size can therefore differ from the size subsequently supplied to the encoder.

**Fact:** The DXGI path provides a second, distinct route to the same output fields. Initialization at `0x33620` calls the monitor refresh routine `0x324d0`, which stores the selected monitor dimensions at `0x32564`/`0x3257c`. It uses them for capture initialization, bitmap allocation and encoder initialization. Its display-attachment path reads client dimensions at `0x31ece` onward, while `CMultiDisplay::FindBestResolution` at `0x42530` enumerates Windows modes and ranks candidates. The requested client pair is therefore an input to display policy, not a guarantee of a particular Windows mode.

**Fact:** The ordinary JPEG initializer at `0x3b750` copies its width/height arguments to encoder-object `+4/+8`. Encoding at `0x3b830` uses those fields when creating the GDI+ destination bitmap and saves the result through the image encoder. Capture resize/reinitialization paths also pass current shared `+0x1c/+0x20` to encoder initialization and recreate the bitmap/buffer. The inspected LCI capture routine at `0x36600` uses those dimensions for its frame copy or BitBlt fallback. These uses support current capture/output dimensions, not a JPEG-stage conversion from the original client pair.

Primary dossiers: sizing `ev_9813d09fb5eca0289518bb349c3aadaa42a326733638c626272aef0cfa084774`; LCI refresh `ev_c7ba671b026581c8a17d8eaab0d9ba2603d3f2b01be337f138d331183d7be6fe`; generic monitor refresh `ev_bdde190b910611bb94d717ceaed30a31d17d382a81b4f8e045a26b2c341aa6d4`. Independent bounded instructions and `encoder-rtti.json` are retained in R.

## Explanation, limits and next discriminating observation — FED-SIZE-E003

**Observed:** Startup supplies 2048×1536. The same run's physical-screen probes report 1280×960; `baseline-after/displays.json` also reports the LuminonCore IDDCX adapter at 1280×960. All 1,903 JPEG records declare 1280×960, and the selected samples match that desktop's controlled content.

**Supported explanation:** client dimensions, a backend's initial requested dimensions, and current monitor/encoder dimensions are separate stages. The shared output fields can be overwritten from monitor measurements before JPEG initialization. Consequently 2048×1536 client dimensions and 1280×960 JPEGs are compatible with the program's data flow. The LCI path specifically contains an intermediate 1600×1200 policy result; treating 1280×960 as the direct result of that helper would be incorrect.

**Unresolved:** The preserved Winsock trace does not record the selected captor, the relevant shared-state values at encoder entry, complete enumerated display modes, or the driver/Windows decision that produced 1280×960. A present LuminonCore adapter does not prove the LCI branch executed. Historical DPI-sensitive 1600×1200 versus physical 1280×960 observations do not prove that DPI caused this sizing transition. No runtime 5/8 or 4/5 scale factor, precise backend selection, or differential-JPEG behavior is claimed.

If that final attribution is required, the next Windows observation is now narrow: record the actual capture-class vtable and shared-state pointer; read `+0x14/+0x18`, `+0x1c/+0x20`, `+0x40`, `+0x64/+0x68` at encoder selection/initialization; and, if LCI is selected, compare the sizing-helper return with monitor-refresh output. Correlate the selected monitor rectangle, Windows mode and calling thread's DPI context with the existing JPEG boundary. This is a passive branch/value question; it requires no invented messages or alternate-mode stimulus. No new Windows capture or cable cycle was performed here.

**Preservation:** `R/integrity-receipt.json` rechecks all 1,993 bundle files (267,923,416 bytes including both manifests) and 512 directories against the original complete inventory, with no changes. The study and vendor hashes remain identical after analysis. New evidence is indexed privately; original captures, failed controls and earlier analysis remain intact. Repository changes are documentation only. Ghidra's recovered types, missing implicit arguments, unresolved virtual calls and erroneous no-return annotations were not treated as runtime proof; decisive branches/stores were checked against instructions.
