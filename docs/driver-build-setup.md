# Driver Build Environment — Setup Notes

**Project:** HASHI (Host Adapter for Splashtop Hardware Interop)
**Purpose:** Build Microsoft's official IDDCX sample driver, with full debug symbols, to use as a labeled ground-truth baseline for binary diffing against `lci_iddcx.dll`.

This is a prerequisite step for the binary-diffing methodology described in `reverse-engineering-methodology.md` — it does not touch Splashtop's driver at all. Everything here is building and inspecting Microsoft's own open-source sample.

---

## Why build the sample at all

Binary diffing only works if one side of the comparison is *labeled*. Without a symboled baseline, there's no way to tell which code in `lci_iddcx.dll` is Microsoft's IddCx framework boilerplate and which is LuminonCore's actual contribution.

Illustrative example — both `sample.dll` and `lci_iddcx.dll` implement `EvtIddCxMonitorAssignSwapChain()`. Microsoft's version is plausibly just:

```
AcquireSwapChain();
while (running) {
    ProcessFrame();
}
```

LuminonCore's version plausibly extends it:

```
AcquireSwapChain();
InitializeEncoder();
while (running) {
    ProcessFrame();
    Encode();
    SendUSB();
}
```

The sample lets us subtract the boilerplate — `AcquireSwapChain()` and the frame loop shape are Microsoft's; `InitializeEncoder()`, `Encode()`, `SendUSB()` are the actual research target.

## What the WDK is, and why GCC can't build this

The Windows Driver Kit (WDK) is Microsoft's SDK for kernel and driver development — headers, libraries, driver templates, build tools, sample drivers, Visual Studio integration, signing utilities. Without it, nothing knows how to compile a driver project.

The sample uses IddCx-specific types and functions that exist *only* in the WDK's headers/libs:

- `IddCxAdapterInitAsync()`
- `WdfDeviceCreate()`
- `IDDCX_SWAPCHAIN`
- `EVT_IDD_CX_MONITOR_ASSIGN_SWAPCHAIN`

No compiler can resolve these without the WDK's headers and import libraries — this isn't a GCC limitation, it's a missing-dependency problem regardless of toolchain.

Three components work together:

| Component | Role |
|---|---|
| Visual Studio Community | IDE / build orchestration |
| Windows SDK | Normal Windows application development |
| Windows Driver Kit (WDK) | Driver-specific headers, libs, templates, signing tools |

"Building" here means compiling Microsoft's sample exactly as intended — not writing new code, the same way building the Linux kernel from source doesn't mean writing it.

## Why Debug, not Release

Release binaries strip names down to raw addresses and generated labels:

```
FUN_18003f210
```

Debug binaries retain real names:

```
EvtIddCxMonitorAssignSwapChain
```

This distinction is the entire point of building a labeled reference — a Release build would defeat the purpose.

## What a PDB is

A PDB (Program Database) is everything the compiler normally discards when producing a binary: function names, variable names, structure/enum definitions, source filenames, line numbers, type information. The CPU only ever sees addresses (`0x180023450`); the PDB is the separate file that maps those addresses back to human-meaningful names.

Ghidra reads PDBs directly — importing one turns `FUN_180012340` into `EvtIddCxMonitorAssignSwapChain` throughout the whole disassembly.

Vendors, including LuminonCore/Splashtop, don't ship PDBs publicly — that's expected and normal (it's exactly what makes reverse engineering necessary in the first place). Microsoft does publish PDBs for many of its own binaries via its public symbol server, but that doesn't extend to third-party drivers built on top of its frameworks.

## The plan this build step feeds into

```
Microsoft Sample
      ↓ build (Debug, /DEBUG)
sample.dll + PDB
      ↓ import into Ghidra, load PDB
Fully symboled disassembly
      ↓ study architecture, confirm IddCx object lifecycle in practice
Only THEN
      ↓
Open lci_iddcx.dll in Ghidra, diff against the sample
```

This is the textbook-before-implementation approach — understand Microsoft's intended shape first, so LuminonCore's deviations from it are obvious rather than needing to be discovered cold.

---

## Setup Checklist

Install only — do not build yet. Verify the environment before moving to the sample project.

- [ ] Visual Studio 2022 Community
- [ ] Windows SDK (version matched to the IddCx target — see version note below)
- [ ] Windows Driver Kit (WDK), version compatible with IddCx 1.2

**Version note:** `lci_iddcx.inf`'s `UmdfExtensions = IddCx0102` (per the original reversing devlog) pins the real Splashtop driver to IddCx 1.2 — an older, narrower feature set than current IddCx versions. Cross-reference Microsoft's IddCx version table to identify which WDK/SDK release shipped IddCx 1.2, and prefer that version for the sample build so the comparison baseline matches Splashtop's actual target rather than a newer framework surface Splashtop's driver can't use.

## Next Steps (once installed)

1. Verify the installed toolchain is correctly recognized (Visual Studio can see the WDK, driver project templates are available).
2. Clone `Windows-driver-samples`:
   ```
   git clone https://github.com/microsoft/Windows-driver-samples
   ```
3. Locate the sample at `video/IndirectDisplay/`.
4. Inspect the project structure before compiling — understand what's in it before building it.
5. Build in **Debug** configuration with `/DEBUG` enabled, producing both `sample.dll` and its matching `.pdb`.
6. Proceed to the binary-diffing workflow (Ghidra Version Tracking, then BinDiff/BinExport) described in `reverse-engineering-methodology.md`, using this build as the labeled baseline against `lci_iddcx.dll`.
