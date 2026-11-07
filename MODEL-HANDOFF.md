# HASHI continuation prompt

Copy the prompt below into the next model's session. It assumes the same working
directory, repository and private evidence remain available. **Inspect the actual
Git state rather than inventing a commit hash or assuming later edits are absent.**

---

Continue HASHI in `/home/noobiegg/Documents/github-stuff/hashi` on Fedora.
Preserve the current repository, private evidence and working Windows
installation. Read any applicable repository instructions, inspect `git status`,
the branch, remotes and recent commits, then read
`docs/fedora-mode-selection.md`, the top of `docs/fedora-startup-validation.md`,
the top of `docs/fedora-next-steps.md` and the top of `RETURN-TO-WINDOWS.md`.
`docs/windows-startup-framing.md` holds the existing capture boundary and
`docs/fedora-backend-import.md` the import receipt. Label meaningful conclusions
**Fact**, **Inference** or **Hypothesis**, and keep evidence IDs, hashes, UTC
timestamps, RVAs and limitations.

## Completed work: do not restart it

- The Windows capture, framing and image validation are complete:
  WIN-START-E001–E005 and FED-FRAME-E001. 1,903 tag-6 JPEG records, exact
  record boundary, twelve decoded pixel-matched samples.
- The live REA/Ghidra study check is complete and **must not be repeated**; the
  study DLL must not be rebuilt.
- The Windows backend observation is complete: WIN-BACKEND-E001–E004. The live
  captor was **LCI** (vtable RVA `0x1ac4b4`) and the encoder was **ordinary
  JPEG** (vtable RVA `0x1ac818`). `InitCaptor`'s failed-initialization fallback
  is **StVD** (`0x37f10`), correcting the older OSBase claim.
- The mode-selection chain is traced: **FED-MODE-E001**. See below. Do not
  re-derive it.
- The 2026-11-07 backend transfer is imported and fully verified (138 payloads,
  98 indexed files, bundle fast-forwarded to `4193abc`). The archive was
  deleted after verification; do not look for it.

## What FED-MODE-E001 settled

**Fact:** The output dimensions reaching ordinary JPEG initialization are the
selected monitor's `rcMonitor` extent from `GetMonitorInfoW` — record append
`0x3ca00` stores `right - left` at record `+0x10` and `bottom - top` at `+0x14`;
getters `0x3cde0`/`0x3ce50` feed shared `+0x1c`/`+0x20`. The LuminonCore
rectangle `[1920,0,3200,960]` gives exactly the observed 1280×960. The captor
reads the mode; it does not request it.

**Inference:** `CCaptor::CustomizeResolution` `0x32590` and `RestoreResolution`
`0x32830` are the captor's only `ChangeDisplaySettingsExW` paths and both require
`shared[+0x44] != 0`, while the LCI rung requires `+0x44 == 0` and `MirrorMode`
was 0 — so they cannot have set the mode. `CMultiDisplay::FindBestResolution`
`0x42530`, reconstructed from instructions, selects 1600×1200 rather than
1280×960 for this client.

**Fact:** The mode was already 1280×960 at `16:15:46Z`, before the
`16:17:54Z`–`16:19:55Z` trace window. A reconnect that starts with the display
already attached contains no mode decision to observe.

**Fact (user-reported):** the 1280×960 mode was the **user's own choice** in
Windows display settings — the size they want for the iPad — persisted by Windows
for `LCI\IDDCX`. **The sizing question is closed and needs no Windows access.**
Do not plan a registry check, a persisted-mode check, an attach transition or any
instrumentation for it. `ForceResW`/`ForceResH` stay unqueried but cannot matter
(`CustomizeResolution` needs `MirrorMode != 0`; LCI needs `MirrorMode == 0`).

**Still open, all answerable offline:** where `AttachExtendDisplay`'s requested
size comes from; the unclassified `ChangeDisplaySettingsExW` sites; the
enumerator's ordering contract; whether the reconstructed score formula is
numerically exact.

## Private evidence and identity

Let `D` be `/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z`
and `B` be `/home/noobiegg/HASHI-private/imports/backend-20261107-20261107T170633Z`.

- `D/bundle` holds the original verified Windows evidence (1,993 files, 512
  directories) plus the agent and study DLL. Do not alter, replace or clean it up.
- `B/bundle` holds the 2026-11-07 transfer: `private-evidence/backend-20261106`
  with its verified 98-file `evidence-index.json`
  (SHA-256 `f9fcdb8493d4dd8c30c6827b660ab7cf01d87e5d9171ef6cd1f4e5b29fd8981b`),
  the retained **failed** first probe, raw traces and receipts.
  `B/import-verification-receipt.json` records the whole import.
- `B/analysis/mode-chain-20261107T171124Z` is the FED-MODE-E001 run; its
  `evidence-index.json` has SHA-256
  `d107f65f6638bc2a6eefb09a7f16738979fdc5d3f6dcca8325396f90fccfe153`. It holds
  the focused asm extracts, the full private disassembly and the score
  reconstruction. Read it before repeating any static work.
- Agent: `D/bundle/private-evidence/windows-runs/20261031-184820/binaries/SWXDAgent.exe`,
  SHA-256 `cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c`,
  `pei-i386`, preferred base `0x400000`. **Never execute it.** Static
  disassembly with `objdump` on Fedora is how it has been read so far.
- Study DLL: `D/bundle/.../study-build/ex06_hashi.dll`, SHA-256
  `6ccab14ea52e7b5f9d858bc98be43a946ca48f68083a1f54a76c0d0524546786`. Preserve;
  do not rebuild.

Private directories are 0700 and files 0600. Do not stage binaries, raw
captures, decompiler output, receipts or instrumentation artifacts; `.gitignore`
covers `/hashi-stuff/`, `__pycache__/` and `*.pyc`, and private evidence lives
entirely outside the checkout. Create a fresh private run directory for new work
rather than writing into an existing one.

## Repository code

`hashi_framing.py` is the validated record-boundary and JPEG-header parser;
`hashi_mode.py` holds the FED-MODE-E001 dimension rules, with the reconstructed
`FindBestResolution` scorer clearly marked **Inference** and deliberately not
wired into anything. Tests live in `tests/` and are run with
`python3 -m unittest tests.test_hashi_framing tests.test_hashi_mode` (21 tests,
passing). Reuse these rather than rewriting them.

## Next task, in order — there is no pending Windows work

1. **Decode the startup state machine at RVA `0x303f0`.** One 0x792-byte,
   563-instruction function holds every observed host→iPad send (`0x30476`,
   `0x30592`, `0x306e7`, `0x30837`) plus reply handling; receive helper is
   `0x112e8`. The agent *is* the host, so this is host-side protocol logic.
   Establish per-field semantics, which replies are validated and how, failure
   and timeout behaviour, and the meaning of the `05 00 00 00` bytes in the
   fourth send. Static only.
2. **Build a byte-exact offline harness.** Re-serialise the captured outgoing
   stream from the host-side model and diff against the capture bytes. This
   validates an implementation without sending anything to the iPad, and keeps
   step 1's inferences from drifting into assumption.
3. `AttachExtendDisplay` callers and the unclassified `ChangeDisplaySettingsExW`
   sites, to bound the FED-MODE-E001 claim by evidence.
4. The capability/`diff_jpeg` parser, and the constant DQT/DHT tables and 4:2:0
   sampling a host would emit (already established across all 1,903 frames).
5. Reconcile new evidence with explicit Facts, Inferences and unknowns. Target
   size for the host is **1280×960**, the user's stated requirement.

## Constraints

Do not execute transferred Windows binaries. Do not change drivers, display
settings, pairing or the vendor installation. Do not send a Fedora-side startup
replay to the iPad — the user declined that path. Do not implement guessed
handshake, resize, codec or control messages. Do not repeat a cable cycle to
re-prove framing, transport or the study check. Do not push without explicit
instruction; no push has been requested, and `refs/backup/pre-backend-import-20261107`
retains the pre-import head.
