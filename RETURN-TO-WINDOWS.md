# HASHI: resume on Windows after the Fedora investigation

Prepared 2026-11-01. This file and the accompanying directory are the complete context for the next Windows Codex session. Proceed with the work, not just a plan.

## Objective and current priority

Implement a Linux host compatible with the **unmodified Splashtop Wired XDisplay iPad app over USB**. **Fact:** No Linux host implementation or validated application protocol exists yet.

**Next question:** Does the observed agent-to-Apple loopback connection carry XDisplay session data, or only control traffic? Fedora static analysis identified specific call sites for a Windows runtime experiment. Do not implement a speculative protocol.

Read these files completely, from the workspace containing this file:

1. `WINDOWS-CODEX-HANDOFF.md` — governing corrections and background.
2. `docs/windows-investigation.md`
3. `docs/windows-components.md`
4. `docs/protocol-observations.md`
5. `docs/windows-next-steps.md`
6. `docs/fedora-investigation.md` — newer static findings, hashes and limitations.
7. `docs/fedora-next-steps.md` — especially **WIN-NEXT-01** and its RVA table.

This return handoff determines the execution environment: **Windows**, not Fedora. New observations supersede older plans. Do not repeat completed Windows setup or follow Fedora prerequisite-installation instructions on Windows. Do not assume the current machine is a VM.

## Locate and preserve the transferred evidence

The outer directory/ZIP may be named `hashi-stuff`. Discover the workspace by this file and `docs/fedora-investigation.md`, rather than relying on the outer directory name. Within that workspace, expect:

```text
RETURN-TO-WINDOWS.md
WINDOWS-CODEX-HANDOFF.md
docs/
hashi-stuff/                         # private transfer material, ignored by Git
  hashi-main/                       # older Windows workspace, not the new root
    scripts/                        # original Windows observation helpers
  HASHI-private/
    runs/20261031-184820/
      binaries/SWXDAgent.exe
      binaries/libusbmuxd.dll
      study-build/ex06_hashi.dll
      analysis/                     # original Windows REA evidence
    tools/rea-6.8.0/
  FEDORA-private-20261101.zip
  FEDORA-private-20261101.zip.sha256
```

**Fact:** The nested Fedora ZIP was created for this return transfer. It is **not** the missing original Windows-to-Fedora archive. Its SHA-256 is:

```text
900a096b2efd0b29667790bc35b28d6fce1ba9c936189b273205e45c912ba9f2
```

It contains 37 files: Fedora raw analysis, setup diagnostics, original-file manifest, evidence index, verification record and historical path mapping. Every archived file was compared with its source. The binaries and original Windows evidence remain in the sibling `HASHI-private` tree; they are not duplicated in this nested ZIP.

Preserve the outer archive and record its SHA-256 if it is locally available. Verify the nested ZIP hash before extracting. Inspect member names and types, reject path traversal/absolute paths/links, and extract into a **new private directory outside the source workspace**, preferably under the existing `C:\Users\noobieGG\HASHI-private` if that path is actually present and suitable. Never overwrite the old Windows run or an existing import.

Verify `evidence-index.json` against the extracted Fedora files. Original artifact hashes are in `docs/fedora-investigation.md`; the original 32,279-file manifest covers the earlier transfer tree, before the new Fedora ZIP was added. Do not count new packaging files as missing original evidence. Its `HASHI-private/...` and `hashi-main/...` relative paths are rooted at the workspace's nested `hashi-stuff` directory.

Map historical `/tmp/HASHI-private-fedora-20261101-9i_xb6aj/analysis/...` to the extracted Fedora bundle's `analysis/...`. Map its former `staging/HASHI-private/runs/20261031-184820/...` to the transferred Windows run or a verified existing private copy. Record the new Windows paths. Linux paths inside raw output are provenance, not paths that must exist on Windows. The private PE helper also contains historical Linux paths; preserve it and adapt a separate copy only if needed.

Keep all subsequent binaries, captures, traces and decompilation outside the source repository. The ignored nested transfer directory is included only to transport existing private evidence. Do not publish this whole ZIP or force-add its contents to Git. Preserve existing workspace changes, user configuration and any existing Git remote; do not invent a remote or overwrite the user's older Windows workspace.

## Reuse the working Windows setup

REA repository: **https://github.com/morluto/rea**; npm package `rea-agents`, CLI `rea`.

**Fact (previous Windows session):** REA 6.8.0, Ghidra 12.1.2 and full JDK 21.0.12 were installed and the study DLL was successfully analyzed through Codex's actual MCP connection. Historical locations and verification Evidence IDs are in the Windows documents. Discover and reuse those installations; do not assume transferring a directory transfers an active MCP connection.

Check the current Codex MCP tools and their live schemas. Verify a small actual REA call. If registration is missing, inspect current requirements, preview a Codex-only setup transaction, preserve existing configuration and apply the authorized setup under current permissions. If reconnection is needed, document the exact step and continue independent inspection. Shell doctor or a standalone SDK connection alone is not the live Codex check.

Use the **transferred** study DLL for any necessary provider check, without rebuilding it. Verify its hash, discover its exports, obtain instructions/pseudocode for a returned function, export evidence privately and close the session. Preferred image base `0x180000000`; add/tick RVAs `0x1000`/`0x1050`. Treat the inherited `void` return inferred for `hashi_tick` as an error to check against source and instructions.

## Execute the focused investigation

**Fact (Windows observations):** Agent product version `1.5.8.3`, file version `1.58.9.6924`; agent and loaded libusbmuxd are x86. An agent connection to Apple Mobile Device Service at `127.0.0.1:27015` disappeared and returned during one cable cycle while both PIDs persisted. The user reported a working extended display. Active Apple device services were WINUSB/usbccgp, driver version 538.0.0.0; bundled usbaapl64.sys was not established as active.

**Inference from Fedora instructions:** The agent can pass the socket returned by `usbmuxd_connect` directly to Winsock send/recv. Hooking only libusbmuxd's send/recv exports can miss this path. No runtime payload or numeric device-side port has been established; 27015 is the local Apple-service endpoint.

Follow **WIN-NEXT-01** in `docs/fedora-next-steps.md`. Rediscover current PIDs, binary hashes, module load bases, available capture/debugging tools and working display state. Use the verified x86 module-relative RVAs; do not use preferred static addresses as live addresses without ASLR adjustment. Record the connect arguments/returned socket, associate it with a loopback connection, and observe direct Winsock I/O during a static test image and one controlled small-region image change. Repeat the image-change trial. Ask the user for cable/iPad actions only when needed; continue independent work while waiting.

Capture successful byte counts and return values, not just requested lengths. Keep raw payloads private and use test content. Account for TCP reassembly, partial I/O, socket reuse and trace overhead. Keep USB transfers, usbmux control, application messages and video frames distinct. If new capture-driver installation or a disruptive change is necessary, explain the concrete action and follow applicable permissions before disturbing the working setup.

Work autonomously on ordinary inspection, local setup, focused static analysis and documentation. Do not bulk-decompile the application or prioritize kernel-driver reversing. Mark every meaningful conclusion **Fact**, **Inference**, or **Hypothesis**, retaining hashes, Evidence IDs, timestamps, RVAs, supporting instructions and limitations. Update the Windows investigation/protocol notes and next-session handoff with what actually ran, what remains unknown and the next discriminating observation. Do not claim Fedora or a VM reproduced Windows runtime behavior.
