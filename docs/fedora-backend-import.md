# Fedora import of the Windows backend transfer — 2026-11-07

Event times are UTC. This records the Fedora-side receipt and verification of
`hashi-backend-fedora-20261107.zip`. The archive itself was deleted after its
extracted contents were verified byte-for-byte; the verified copy is the
preserved original. No private evidence is stored in Git.

## Archive receipt

**Fact:** The transfer archive was 1,567,390 bytes with SHA-256
`08d8b18b056191959bb88933d7657930d88d47ed0dfdc795d7c96ee12c5b0a43`, matching the
value supplied with the transfer.

**Fact / limitation:** No `.sha256` sidecar file accompanied the archive. A search
of `/home/noobiegg` to depth 4 found only the ZIP. The hash was therefore
verified against the value supplied in the session instruction, not against a
transferred sidecar. The archive's own integrity is established; the absence of
an independent sidecar is recorded so it is not later mistaken for one.

## Pre-extraction member audit

**Fact:** All 139 members were inspected from the central directory before any
extraction. Counts of zero were recorded for absolute paths, drive letters,
backslash separators, `..` traversal components, names that escape the
extraction root after normalisation, control characters, non-ASCII names,
symlink entries, non-regular (special) file entries, setuid/setgid/sticky modes,
members above 8 MiB, encrypted members, members using compression other than
stored/deflate, and duplicate member names. Uncompressed size totalled 9,328,788
bytes (8.90 MiB) and the worst single-member compression ratio was 22.8x, so no
expansion bomb was present. Extraction proceeded only after this audit passed.

**Fact:** After extraction, 139 regular files were present with zero symlinks and
zero non-regular files, confirming the audit's prediction.

## Destination and preservation

**Fact:** Extraction used `unzip`, which preserves recorded modification times,
into a new private directory outside the checkout:

```text
/home/noobiegg/HASHI-private/imports/backend-20261107-20261107T170633Z
```

Its `bundle/` subdirectory holds the archive contents; `import-verification-receipt.json`
holds the machine-readable receipt. Directories are mode 0700 and the receipt is 0600.

**Fact:** The earlier Fedora import at
`/home/noobiegg/HASHI-private/imports/windows-20261105-20261105T072144Z` was not
touched, overwritten or cleaned up, and the earlier Windows evidence it contains
retains its own hashes.

## Payload verification

**Fact:** `transfer-manifest.json` (created `2026-11-07T16:35:47.252775+00:00`)
declares 138 payloads. All 138 verified by SHA-256 and byte length: zero
mismatches, zero missing, and zero files on disk absent from the manifest. The
manifest records source checkout `C:\Users\noobieGG\Downloads\hashi\hashi` and
source evidence `C:\Users\noobieGG\HASHI-private\runs\backend-20261106`.

**Fact:** `private-evidence/backend-20261106/evidence-index.json` has SHA-256
`f9fcdb8493d4dd8c30c6827b660ab7cf01d87e5d9171ef6cd1f4e5b29fd8981b`, matching the
expected value. It carries evidence ID `WIN-BACKEND-E001`, indexed
`2026-11-07T16:23:11.755737+00:00`, and agent SHA-256
`cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c` — the unchanged
x86 agent. All 98 indexed files verified against the index: zero mismatches,
zero missing.

**Fact:** The five artifacts named by hash in
[Fedora startup validation](fedora-startup-validation.md) were independently
re-hashed from the import and all five match the committed documentation:

| Imported file | SHA-256 | Role |
| --- | --- | --- |
| `backend-trace.jsonl` | `f346fd0c…49683d` | Retained **failed** first probe |
| `backend-current-trace.jsonl` | `35c4eba5…25f2a2` | Clean 8-second current-state run |
| `backend-init-trace.jsonl` | `ab46b96e…86c455` | Successful initialization trace |
| `backend-init-analysis.json` | `72b20fe3…214e4d` | Derived analysis |
| `display-post-reconnect.json` | `3ce2f821…38b6cd` | Post-reconnect display snapshot |

The failed probe, raw traces and receipts are preserved; none were regenerated.

## Git integration

**Fact:** Before integration the checkout was on `main` at
`b3c0cfbbd9b72d509d9da5a6917e02679e49de77` with a clean tree apart from the
untracked transfer archive. Remote `origin` is
`https://github.com/ASPRNG-PRGMR/hashi.git`.

**Fact:** `hashi-backend.bundle` has SHA-256
`7e474305286217443038de90ba784b77d9e42e9a7b69982aaaa9e51f4c1c80d1`, matching the
manifest. `git bundle verify` reported `okay`, declaring prerequisite
`b3c0cfbbd9b72d509d9da5a6917e02679e49de77` and tip
`4193abc29a18676d7874e8a5be9af83b7db2a4f7` with hash algorithm sha1. The
prerequisite equalled the local head exactly.

**Fact:** The bundle was fetched into the separate ref
`refs/imported/backend-20261107` rather than directly onto a branch. It
introduced exactly two commits:

- `0274bbbea0f3a93267ab2f55c18153ad6840f8bc` — *docs: record Windows backend selection and sizing evidence* (`docs/fedora-next-steps.md`, `docs/fedora-startup-validation.md`)
- `4193abc29a18676d7874e8a5be9af83b7db2a4f7` — *docs: hand off confirmed Windows backend result* (`RETURN-TO-WINDOWS.md`)

Both are documentation-only: three Markdown files, 30 insertions and 2 deletions,
with no binary content, no file-mode changes and no added or removed paths.

**Fact:** Because the local head was exactly the prerequisite and no local commits
existed beyond it, integration was a fast-forward to
`4193abc29a18676d7874e8a5be9af83b7db2a4f7`. No local commit, file or edit was
discarded. The pre-import head is additionally retained at
`refs/backup/pre-backend-import-20261107`. **No push has been performed or requested.**

## Private evidence policy

**Fact:** The 137 `private-evidence/` members and `transfer-manifest.json` remain
outside the checkout. Only the bundle's three documentation files entered Git.
`.gitignore` continues to exclude `/hashi-stuff/`, `__pycache__/` and `*.pyc`.
Do not stage raw traces, decompiler output, instrumentation scripts, vendor
binaries or receipts.

**Fact:** No transferred Windows binary was executed. The import contains a
Windows `capstone.dll` (7,574,016 bytes) and `.pyc` files inside `python-deps/`;
these were hashed only and never loaded. No driver, display setting, pairing or
vendor installation was changed, no Fedora-side startup replay was sent to the
iPad, and the completed REA study check was not repeated.
