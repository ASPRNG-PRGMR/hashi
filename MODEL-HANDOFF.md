# HASHI continuation prompt

Copy the prompt below into the next model's session. It assumes the same working directory, repository and private evidence remain available. The commit containing this file also records the completed REA connection check and dimension/encoder investigation; its parent is `26fc99c`. Inspect the actual Git state rather than inventing a commit hash or assuming later edits are absent.

---

Continue HASHI in `/home/noobiegg/Documents/github-stuff/hashi` on Fedora. Preserve the current repository, private evidence and working Windows installation. Read any applicable repository instructions, inspect `git status` and recent commits, then read `docs/fedora-startup-validation.md` completely and the current update at the top of `RETURN-TO-WINDOWS.md`. Read `docs/windows-startup-framing.md` for the existing capture boundary. Current findings supersede the historical REA-disconnected and downstream-analysis TODO statements in older handoffs.

## Completed work: do not restart it

- The Windows capture was imported and reproduced offline: exact stream consumption, 1,903 1280×960 JPEG records, and twelve decoded samples matching independently checked desktop changes.
- The actual Codex REA MCP connection passed, reporting REA 6.8.0, Ghidra 12.1.4 and an aligned `codex-mcp-client`. The unchanged study DLL was opened, its returned `hashi_add` and `hashi_tick` addresses analyzed, evidence exported, and the session closed. Final session status was `open=false`, `cleanup_pending=false`.
- The DLL was **not rebuilt**. `hashi_tick` retains the `GetTickCount` EAX return despite Ghidra's incorrect `void` pseudocode. Recovered types and no-return annotations are not authoritative; check decisive instructions.
- The vendor field trace is documented as FED-SIZE-E001–E003. No vendor target was executed on Fedora and no protocol messages were implemented or transmitted.

## Private evidence and identity

Let D be `/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z`.

- Original evidence: `D/bundle`, verified unchanged against `D/hashi-initial-verification.json`: 1,993 files and 512 directories. Do not alter, replace or clean it up.
- New analysis R: `D/analysis/rea-dimensions-20261105T140157Z`. Read its `evidence-index.json`, `integrity-receipt.json`, `preservation-receipt.json`, `export-checks.json` and session identity receipts. All 25 indexed files and the index were copied and hash-verified; the durable preservation receipt is additional. Private directory mode is 0700 and files are 0600.
- `R/study-evidence.json`: seven REA records. `R/agent-evidence.json`: 47 REA records. Bounded assembly extracts, RTTI verification and the instruction search index remain private. Use these before repeating analysis.
- Agent: `D/bundle/private-evidence/windows-runs/20261031-184820/binaries/SWXDAgent.exe`, SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`.
- Study DLL: `D/bundle/private-evidence/windows-runs/20261031-184820/study-build/ex06_hashi.dll`, SHA-256 `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. Preserve it; do not rebuild it.
- Startup capture: `D/bundle/private-evidence/windows-runs/startup-20261105-103819`. Earlier runs and negative controls remain preserved.
- Temporary working evidence also remains at `/tmp/hashi-rea-20261105-mKbn3t`; prefer the durable copy. Its preservation script deliberately refuses an existing destination. Do not rerun it as an update mechanism.

Do not stage binaries, raw captures, decompiler output, private receipts or instrumentation artifacts. Create a fresh private run for new work. Respect the actual filesystem permissions; writing outside the workspace may require escalation even though preserving private evidence is authorized. No push or publication is requested.

## What the dimension and capability trace actually establishes

All vendor code locations below are module-relative **RVAs**. The static preferred base is `0x400000`; add the actual loaded module base for Windows hooks. Do not confuse the connection object's `+0x1c` shared-state pointer with the shared state's `+0x1c` width. Capture objects hold that shared state at `+0x88`.

| Shared-state fields | Established use |
| --- | --- |
| `+0x14/+0x18` | Client dimensions, initially 2048×1536 in the capture; also mutable through later event handling |
| `+0x1c/+0x20` | Current capture/encoder dimensions, passed into encoder initialization |
| `+0x40` | Header representation flag in the inspected send path |
| `+0x64` | Encoder selector with priority over `+0x68`; zero takes the JPEG family, nonzero selects SRx264 |
| `+0x68` | Chooses differential JPEG when `+0x64` is zero; otherwise ordinary JPEG is selected |

The sizing helper at RVA `0x31400` maps 2048×1536 to an initial **1600×1200** request. In the LCI path, initialization at `0x35d60` calls that helper at `0x35f0c`, then calls `UpdateMonitorInfo` at `0x36163` before encoder creation at `0x363a3`. `UpdateMonitorInfo` (`0x35b30`) overwrites output dimensions at `0x35c4c/0x35c63` with selected-monitor measurements. Generic monitor refresh (`0x324d0`) does the same through another capture path. Encoder selection is at `0x31900`; ordinary JPEG initialization is at `0x3b750`, with encoding at `0x3b830`.

The existing capture proves a 1280×960 desktop and 1280×960 JPEGs. It does **not** prove which captor ran or why Windows/the driver selected 1280×960. Do not present a fixed 5/8 scale, a DPI-caused 4/5 scale, or the LCI intermediate size as observed runtime values. The LuminonCore adapter's presence alone does not prove LCI capture selection.

The captured capability body begins with NUL and bypasses the inspected `diff_jpeg` key path. It does not establish successful differential-JPEG negotiation. Tag 6 alone does not distinguish ordinary from differential JPEG in the static selector. The separately transmitted native-order constant 5 still has unknown meaning. Alternate modes remain unobserved.

## Next task, in order

1. Review the retained evidence and prepare a **bounded, passive Windows observation** that can resolve the runtime branch/value gap. Work on Fedora first. Reuse the existing capture tools and matching-build boundaries; inspect their code before extending them. If more static analysis is necessary, discover the currently advertised REA schemas, verify the agent hash, inspect only the missing functions, export new evidence privately and close the session. A healthy connection does not require reinstalling tools or repeating the study exercise.
2. Prepare a reviewable probe and exact run instructions that record the actual capture-class vtable and shared-state identity; the listed dimension/representation/selector fields at encoder selection and initialization; and, **only if LCI runs**, the sizing-helper return and monitor-refresh output. Decode the actual x86 calling conventions from instructions; do not assume every method is ordinary `thiscall`. Bound duration and data volume, preserve original timestamps and hashes, and detach cleanly. Read values; do not mutate them or send extra traffic.
3. Plan correlation with the selected monitor/device, available and current Windows display modes, monitor rectangle, agent/calling-thread DPI context, and the already validated JPEG boundary. Separate an initial requested size from the mode actually applied and later refreshed values. Avoid capturing extra screen content when dimensions and metadata suffice.
4. The current environment is Fedora. Do not assume Windows is remotely reachable or execute transferred Windows tools here. Complete offline preparation first. If the observation still requires access to the working Windows session or a controlled normal reconnection, explain the exact remaining action and why, then request only that prerequisite. Do not repeat a cable cycle merely to re-prove framing, transport or the REA study check.
5. After actual runtime evidence exists, reconcile it into the report with explicit facts, inferences and remaining unknowns. If it does not establish the backend/mode decision, say so. Broader protocol interoperability and alternate capability semantics are later tasks; do not implement guessed handshake, resize, codec or control messages.

Deliver the concrete next experiment/probe and its validation, or the resulting bounded observations if Windows access is actually available and authorized. Preserve private evidence and leave a clear continuation state. This prompt does not authorize changing drivers, display settings, pairing, the vendor installation, or protocol behavior to force an outcome.
