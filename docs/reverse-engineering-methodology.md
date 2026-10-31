# Reverse Engineering Methodology

**Project:** HASHI (Host Adapter for Splashtop Hardware Interop)
**Scope:** How `lci_iddcx.dll` is analyzed against Microsoft's IddCx sample driver, and how findings feed into an open-source Linux reimplementation. Clean-room throughout — no LuminonCore/Splashtop code is ever copied or ported, only observed behavior.

Prerequisite: a Debug build of Microsoft's sample IDD driver with a matching PDB. See [`driver-build-setup.md`](./driver-build-setup.md).

---

## 1. Compare Microsoft's sample IDDCX driver against `lci_iddcx.dll`

**Tools:** Ghidra (free, NSA), plus one of two diffing paths below.

Import both binaries into Ghidra as separate programs in the same project. For the sample driver, load its PDB before running auto-analysis so real function names populate from the start (`EvtIddCxMonitorAssignSwapChain`, not `FUN_18003f210`).

### Diffing path A — Ghidra Version Tracking (built-in, zero extra installs)

1. `Tools → Version Tracking Session...`, sample driver as source, `lci_iddcx.dll` as destination.
2. Run the built-in correlators (Exact Match, Symbol Match, Function Hash) to bulk-match identical/near-identical functions — this is framework glue, deprioritize it.
3. Whatever remains unmatched after this pass is the first candidate list for vendor-specific code.

### Diffing path A′ — find the callback table first (no diffing needed)

An IddCx driver must fill `IDD_CX_CLIENT_CONFIG` (a struct of DDI callback pointers, field order fixed by `iddcx.h`) and pass it to `IddCxDeviceInitConfig`; likewise `WDF_DRIVER_CONFIG` and the PnP/power callback struct for WDF. Framework calls go through per-version function tables (`WdfFunctions_02015` for UMDF 2.15, and the IddCx equivalent) with the driver-globals pointer in RCX. Locating those two tables and the config fill names every framework call and every DDI callback, including `EvtIddCxMonitorAssignSwapChain`, before any diff runs. Do this first; diffing then only has to cover what is left.

### Diffing path B — BinDiff + BinExport (only if it builds against your Ghidra)

**Corrections (2026-10-14):** Diaphora remains IDA-only. BinDiff 8 is the current release, but its **prebuilt BinExport Ghidra extension stops at Ghidra 11.0.3** (April 2024), and google/binexport issue #144 (protobuf mismatch, `IllegalAccessError` on export) is open with activity through late 2025. With Ghidra 12.1.4 this path requires building BinExport's `java/` directory from source against the installed Ghidra and matching its protobuf version. Budget an afternoon; abandon if it fights back. Alternatives in order: Ghidra Version Tracking (path A), Ghidra BSim (built in), `ghidriff` (Python, pyghidra-based; check Ghidra 12 support first).

1. Clone `github.com/google/binexport`, build the Ghidra extension from `java/` with `-PGHIDRA_INSTALL_DIR=...` per its README, matching protobuf to Ghidra's bundled version.
2. In Ghidra: `File → Install Extensions...` → add the BinExport zip → restart Ghidra.
3. Export both binaries: open each in Ghidra's CodeBrowser, `File → Export Program... → Binary BinExport (v2) for BinDiff`.
4. Diff them:
   ```
   bindiff sample_idd.BinExport lci_iddcx.BinExport
   ```
   or use the BinDiff GUI (`File → New Diff`).
5. Read results sorted by similarity **ascending**:
   - **High similarity (>0.9):** framework glue — skip.
   - **Matched, low similarity:** same function shape as the sample, different internals — this is the priority list. Likely candidates: the DDI callbacks LuminonCore actually implements.
   - **Unmatched (secondary only):** functions with no counterpart in the sample at all — pure LuminonCore/Splashtop code (transport, USB handling, encoding).
6. Port matched names back into Ghidra's `lci_iddcx.dll` database via BinDiff's symbol/comment import, so the Ghidra project ends up with framework functions auto-labeled — anything still unnamed afterward is real research territory.

### Suggested order

Run Version Tracking first (free, instant, clears obvious matches) → then BinDiff for the harder partial matches it misses. Start reading from the lowest-similarity *matched* function nearest `EvtIddCxMonitorAssignSwapChain` in the call graph — matched-but-different gives a reference point; a cold unmatched function doesn't.

---

### Priority note (2026-10-14)

The wire protocol HASHI must reproduce is spoken by the Splashtop host agent process to the iPad app over Apple's USB multiplexing, not by `lci_iddcx.dll`. The driver only hands desktop frames to that agent, and `evdi` replaces it on Linux. Treat §1–§2 as (a) the learning vehicle for reading vendor binaries and (b) the way to answer "how do frames reach the agent and in what format". Phase 1 USB capture and §3 (agent ↔ driver IPC) come first on the critical path.

## 2. Identify what LuminonCore changed

Falls directly out of step 1's "unmatched" and "low-similarity matched" buckets:

1. Start from `EvtIddCxMonitorAssignSwapChain` (confirmed frame handoff point per `iddcx-reference.md`) — the diff tool shows what it calls that the sample's version of the same callback doesn't.
2. Follow those unmatched calls outward. Look for: threads spun up, handles opened (file, device, named pipe, socket), and any function touching memory outside the DirectX surface IddCx handed it — that's the boundary where Splashtop's actual transport logic lives.
3. Cross-reference against a WPP trace of the real driver (see `iddcx-reference.md` §4.2) — the trace shows *when* in the frame lifecycle vendor code runs; the binary diff shows *what* that code is. Combined, this produces a labeled call graph instead of a flat list of unknown functions.

Classify every finding Fact / Inference / Hypothesis, consistent with the rest of the project's documentation, and confirm each against runtime behavior (step 3 below) before trusting it.

---

## 3. Trace how the Splashtop host process talks to the driver

Layer cheap tools before expensive ones — each rules things in/out before committing to the next.

**Process Monitor (Sysinternals) — cheap first pass**
Filter on the Splashtop host process and the WUDF host process running `lci_iddcx.dll`. Watch for `CreateFile` on named pipes/devices, `RegOpenKey`, `\Device\` or `\\.\pipe\` paths.

**Process Explorer — handle inspection**
Compare open handles between the Splashtop host and WUDF host side by side. Shared handle types (memory-mapped sections, events, named pipes) are strong evidence of the real transport — a shared memory section in particular would explain frame data crossing the process boundary without a full DDI round-trip.

**API Monitor — if handles don't reveal it**
Traces calls to `ntdll`/`rpcrt4`/`combase`/`ws2_32` from the Splashtop host process, distinguishing between the four candidate IPC mechanisms:

| Mechanism | Signature APIs |
|---|---|
| RPC | `RpcBindingFromStringBinding`, `NdrClientCall*` |
| COM | `CoCreateInstance`, `CoGetClassObject` |
| Named Pipes | `CreateNamedPipe` / `CreateFile` on `\\.\pipe\*` |
| IOCTL | `DeviceIoControl` on the IDD's device interface |
| ALPC | Not visible here — see below |

**WinDbg + kernel debugger — fallback for ALPC**
If nothing above surfaces the mechanism, it's likely ALPC (`NtAlpcSendWaitReceivePort` family), only visible via kernel-level tracing. The same kernel debugger session used for IddCx WPP tracing (`iddcx-reference.md`) can be reused here.

---

## 4. Replace pieces one-by-one with an open-source implementation

**Key principle: never port or transcribe LuminonCore's or Splashtop's actual code.** Only the *behavioral facts* learned from steps 1–3 (protocol shape, transport mechanism, frame format) carry over into HASHI's implementation. This is what keeps the project a legitimate interoperability effort rather than a copyright liability — the same line Samba, Wine, and libimobiledevice draw. Two further rules: raw captures, traces and frame dumps stay out of the public repo; and the study notes describe behavior ("waits on two events with a 16 ms timeout"), never reproduce decompiled vendor source.

Replacement order, matching the phase roadmap in the project README:

1. **Optional Windows-side validation:** build a modified copy of Microsoft's *sample* driver implementing the confirmed DDI sequence and transport behavior. If the real Splashtop iPad app accepts a connection from this harness, the protocol understanding is confirmed before porting to Linux — cheaper to debug on one platform at a time.
2. **Port the confirmed protocol to the Linux daemon** — only the transport/protocol logic (framing, handshake, codec) is reimplemented, never any LuminonCore code, since none of it was copied, only observed.
3. **Swap the display backend independently of the protocol** — `evdi` replaces `lci_iddcx.dll`'s structural role (virtual display + frame delivery); the protocol talking to the iPad is a separate, independently-ported concern.
4. **Validate incrementally against the real iPad app** at each swap: USB pairing layer alone first (does the app see a valid host?), then passive frame delivery (does it accept a stream at all, even a test pattern?), then the real codec.
