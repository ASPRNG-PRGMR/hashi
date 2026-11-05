# Fedora startup validation — 2026-11-05

**Fact:** The November 5 Windows capture reproduces offline on Fedora: 1,903 JPEG records, exact application-stream consumption, and twelve decoded samples matching the controlled square. The source import is committed as `c63c354`. No protocol messages were transmitted or implemented. This report supplements [Windows startup/framing](windows-startup-framing.md); its observations govern the older Fedora plans.

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

## Linux tools and remaining live check — FED-START-E003

**Fact:** Reused the full Temurin JDK 21.0.10 at `/opt/st/STM32CubeMX/jre`. The existing default Node 24.20.0 did not satisfy the pinned REA package. Installed Linux Node 24.22.1, Ghidra 12.1.4 and REA 6.8.0 under `/home/noobiegg/HASHI-private/tools/fedora-20261105`. Node and Ghidra archive SHA-256 values were checked against their official distribution metadata; npm records pinned package integrity. Package installation scripts were disabled. No transferred Windows native tools were executed and the study DLL was not rebuilt.

**Fact:** Scoped `rea doctor --provider ghidra --json` passes Node, Linux architecture, Ghidra version/headless entry, ELF x86-64 decompiler identity and full JDK checks. Unselected optional engines are not required. Codex-only setup was previewed; its single planned action preserves unrelated configuration. The registered launcher is pinned to the absolute supported Node binary so a desktop PATH cannot silently select the older Node. The original config is retained privately in D. See `D/analysis/rea-registration-receipt.json` for the applied registration and checks.

**Fact / remaining limitation:** No REA `binary_session`, `open_binary` or `analyze_function` tools are exposed to this agent. CLI doctor is not a connected-client study check. Reconnect the Fedora Codex client, inspect its actual advertised REA tools, and perform the small study call on `D/bundle/private-evidence/windows-runs/20261031-184820/study-build/ex06_hashi.dll`, SHA-256 `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. Analyze returned `hashi_add`/`hashi_tick` addresses, export evidence privately and close the session. The inherited incorrect `void` tick signature must be checked against its preserved EAX return. [Official Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp) describes stdio registration and the client configuration location.

## Next discriminating investigation

Trace readers of the same connection object's `+0x14`, `+0x18`, `+0x40` and `+0x68` fields to the capture/resize/encoder selection path. Determine how client-reported 2048×1536 becomes the observed 1280×960 JPEG stream, and whether the `diff_jpeg` state can change that selection. Use focused references and bounded functions; retain the alternate mode as unobserved. Keep the working Windows installation for a specific follow-up experiment only if this analysis leaves a concrete behavioral question. No additional Windows cable cycle is needed for this import.

Cleanup is conditional on the final unchanged-bundle and committed-source checks. `D/completion-receipt.json` records the actual result and commit IDs after those gates; no cleanup claim is inferred from this pre-cleanup document.
