# Study Plan — x64 Assembly and Windows Reversing for Reading a UMDF/IddCx Driver

**Project:** HASHI (Host Adapter for Splashtop Hardware Interop)
**Started:** 2026-10-14 (resumption after a break; prerequisite-skills phase)
**Goal:** Enough x64 and Windows literacy to open `lci_iddcx.dll` in Ghidra and read it with confidence, and to read `lci_proxywddm.sys` and the Splashtop host agent later.
**Not the goal:** general exploit development, malware analysis, or kernel internals beyond what these three binaries need.

The hands-on exercise sources that accompanied this plan are not distributed with the
repository; the plan below describes them well enough to recreate them.

---

## 0. Ground rules for this phase

1. **Every assembly claim gets checked against a compiler.** If a video or a book says "the prologue always looks like X", compile a function and look. Compiler Explorer (godbolt.org) with `x86-64 gcc` and `x64 msvc` side by side is the fastest way.
2. **Read decompiler and disassembly together.** Ghidra's decompiler is a hypothesis generator. The disassembly is the fact. When they disagree, the disassembly wins and the decompiler needs a type fix.
3. **Keep the Fact / Inference / Hypothesis labels** for anything you conclude about the real binaries. For study exercises, "I saw it in my own compiled output" is the fact.
4. **Never transcribe vendor code.** Study notes about `lci_iddcx.dll` describe behavior ("opens a section object named ...", "calls the swapchain acquire function in a loop"), never reproduce its instructions or decompiled source in HASHI's own code.

---

## 1. What you need, and what you can skip

### Needed (in the order you'll meet it in the binary)

| Topic | Why it matters for `lci_iddcx.dll` |
|---|---|
| Registers, `mov`/`lea`, memory operands `[base + index*scale + disp]` | Every struct field access is one of these. |
| Microsoft x64 calling convention (RCX, RDX, R8, R9, XMM0-3, 32-byte shadow space, RAX return, callee-saved set) | Tells you which register holds `this`, which holds the WDF object handle, how many arguments a call has. |
| Prologue / epilogue, stack frames, `sub rsp, N`, frame-pointer omission | Lets you separate "bookkeeping" from "logic" at a glance and recognize how many locals a function has. |
| Pointers, structs, arrays, pointer-to-struct chains | WDF and IddCx hand you opaque handles plus context structs; the driver's own state is a struct you have to reconstruct. |
| Function pointers and tables of function pointers | **The** IddCx pattern. The driver registers callbacks by filling a struct of function pointers, and calls the framework through a global function table. This is how you find `EvtIddCxMonitorAssignSwapChain` without a diff. |
| Optimized vs unoptimized code (`-O0` vs `-O2`, MSVC `/Od` vs `/O2`) | The vendor shipped a Release build. You must recognize inlining, hoisting, jump tables, `lea` arithmetic, tail calls. |
| PE format: sections, imports (IAT thunks, `call [rip+X]`), exports, `.pdata` unwind info | Imports tell you what Windows APIs the driver uses (threads, events, sections, sockets) before reading a single function. |
| MSVC idioms: `__security_cookie`, `__chkstk`, SEH/C++ EH tables, CRT startup, `__imp_` thunks | So you don't waste a week reversing the C runtime. |
| C++ in binaries: `this` in RCX, vtables, constructors, `new`/`delete`, STL templates, lambdas as thread functions | Microsoft's own sample is C++ (classes `SwapChainProcessor`, `IndirectDeviceContext`); a vendor driver derived from it will be too. |
| WDF/UMDF patterns: `WdfDriverGlobals` as first argument, `WdfFunctions_02015` table, object context accessors, `WDF_DRIVER_CONFIG` | UMDF 2.15 driver. Every framework call is an indirect call through a version-named table. |
| IddCx patterns: `IDD_CX_CLIENT_CONFIG` callback struct, `IddCxDeviceInitConfig`, swapchain acquire/finish loop | The frame path you care about. |
| Windows user-mode IPC APIs as they look in a disassembly: `CreateFileMappingW`/`MapViewOfFile`, `CreateEventW`, named pipes, `DeviceIoControl`, RPC/COM stubs | To answer the open question "how does the host agent talk to the driver". |

### Skip for now, and why

| Topic | Why skip |
|---|---|
| 32-bit x86, `cdecl`/`stdcall`/`fastcall` differences | All three binaries are x64. x64 Windows has one convention. |
| SIMD/AVX semantics beyond "this moves 16 bytes" | You need to recognize `movups`/`movaps` as memory copies, not understand vector math. Codec work on the Linux side uses libraries. |
| Floating point details (x87, rounding) | Rare in a display driver; recognize `XMM` scalar moves and move on. |
| Kernel-mode concepts (IRQL, DPCs, IRPs, MDLs) | `lci_iddcx.dll` is user-mode. Learn only when you open `lci_proxywddm.sys`, and only what that binary uses. |
| Exploit development (ROP, shellcode, heap grooming) | Different skill. Not needed for interop reversing. |
| Anti-debugging, packers, obfuscation | Driver-signed vendor code is almost never packed. Check entropy once; if it's normal, skip. |
| .NET / managed code reversing | Not present in the driver stack. |
| ARM64 | The observed binaries are x64. |

---

## 2. The four-week plan at a glance

| Week | Theme | Output |
|---|---|---|
| 1 | Reading x64 produced from **your own C**, on Fedora, with Ghidra open | You can read a `-O2` compiled C function with structs and callbacks and reconstruct its C. |
| 2 | Windows flavor: PE, MSVC idioms, C++ objects, Windows API calls | You can take a MinGW- or MSVC-built DLL, list its imports/exports, find `DllMain`, and read a class method. |
| 3 | WDF and IddCx patterns, using Microsoft's sample as the textbook; TryHackMe rooms | Sample driver built in the Win11 VM (Release + PDB, and Debug + PDB), opened in Ghidra, callback table located. |
| 4 | First look at `lci_iddcx.dll`, with a strict checklist and stop conditions | Imports inventory, callback table located, `AssignSwapChain` candidate identified, no code copied. |

Weeks 2–4 are outlines. They get filled in once Week 1 shows what pace is realistic.

---

## 3. Week 1 — day by day

Environment check (already verified on this Fedora box on 2026-10-14): `gcc` 16, `x86_64-w64-mingw32-gcc` 16 (MinGW, builds real Windows PE binaries using the Microsoft x64 convention), `gdb` 17, `objdump`, OpenJDK 25. Ghidra 12.1.4 is **not** installed; it needs Java 21 or newer with no upper bound, so Java 25 works.

### Day 1 — Setup, registers, the four instructions that matter

**Do**
1. Download Ghidra 12.1.4 from the GitHub releases page (`NationalSecurityAgency/ghidra`), unzip under `~/opt/`, run `ghidraRun`. Create a project `hashi-study`.
2. Build every exercise four ways — Linux `-O0`, Linux `-O2`, Windows `-O0`, Windows `-O2`, all with debug info. Also emit Intel-syntax `.s` files for side-by-side reading.
3. Open `build/ex01_basics.s.linux-O0` in a text editor and `build/ex01_basics.linux-O0` in Ghidra. Read `add3` and `main`.

**Learn** (from the Intel/AMD manuals or any x64 video, then confirm in your output)
- The 16 general registers, their 32/16/8-bit sub-names (`rax`/`eax`/`ax`/`al`), and the rule that writing a 32-bit register zeroes the upper 32 bits.
- `mov` (copy), `lea` (compute an address, no memory access), `add`/`sub`/`imul`, `cmp`/`test` + `jcc`, `call`/`ret`, `push`/`pop`.
- Memory operand syntax: `[rbp-0x14]` is a local; `[rcx+0x18]` is a field; `[rax+rdx*4]` is an array element.
- Flags only as far as: `cmp a,b` then `jg` means "jump if a > b (signed)"; `ja` is the unsigned version.

**Check questions** (answer in your notes, then ask me)
1. In `add3` at `-O0`, where do the three arguments land right after the prologue, and why does the compiler spill them to the stack at all?
2. What does `imul eax, edx` compute, and which C expression is it?
3. Why is the function's return value in `eax` and not `rax` here?

### Day 2 — Microsoft x64 calling convention vs System V

**Do**
1. Read `build/ex02_callconv.s.linux-O2` and `build/ex02_callconv.s.win-O2` side by side. Same C, two conventions.
2. In Ghidra, import `build/ex02_callconv.win-O2.exe`. Note Ghidra picks the `__fastcall` (Microsoft x64) convention automatically for PE.

**Learn**
- Microsoft x64: integer/pointer args in RCX, RDX, R8, R9; floating args in XMM0-XMM3 **by position** (arg 2 as a double goes in XMM1, and RDX is unused); 5th+ args on the stack; return in RAX or XMM0.
- The 32-byte **shadow space** (home space): every caller reserves 32 bytes above the return address even for a 0-arg call. That's why `sub rsp, 0x28` is the most common prologue you'll see: 32 bytes shadow + 8 to keep RSP 16-byte aligned at the call.
- Callee-saved (non-volatile): RBX, RBP, RDI, RSI, R12–R15, XMM6–XMM15. Volatile: RAX, RCX, RDX, R8–R11, XMM0–XMM5. If a function uses RBX it must push/pop it, and you'll see that in the prologue.
- System V (Linux): RDI, RSI, RDX, RCX, R8, R9; no shadow space; 128-byte red zone. You only need this to avoid being confused when you compile natively.

**Check questions**
1. `sum6` takes six `long`s. Under Windows, where are args 5 and 6 when the function starts executing? Give the `[rsp+...]` offsets.
2. `mix(int, double, int, double)`: list the register for each of the four arguments under Windows, then under Linux.
3. A function body contains `mov [rsp+0x8], rcx` as its first instruction. What is it doing and what does it tell you about the compiler settings?

### Day 3 — Prologues, epilogues, frames, locals

**Do**
1. `ex03_frames.c` has a 64-byte local buffer and nested calls. Compare `-O0` and `-O2` on both targets.
2. In Ghidra, open `work` and use the **Stack frame editor** (right-click the function → Edit Stack Frame) to see how Ghidra laid out locals. Rename `local_48` to `local_buf` and set its type to `char[64]`.

**Learn**
- Frame with RBP (`push rbp; mov rbp, rsp; sub rsp, N`) vs frame-pointer omission (just `sub rsp, N`; locals addressed from RSP). MSVC Release uses RSP-relative almost everywhere.
- How to compute frame size from the prologue and how to map a `[rsp+0x20]` reference to "local or shadow space of the next call".
- Epilogue mirrors the prologue; `ret` is the end. Multiple `ret`s in Release code are normal.
- Stack cookies: GCC emits `__stack_chk_fail`; MSVC emits `__security_cookie` xor + `__security_check_cookie`. Both exist because of the `char[64]` local. Recognize and ignore.

**Check questions**
1. For `work` at Windows `-O2`, what is the total frame size, and how many of those bytes are the local buffer versus shadow space for `strlen`/`checksum` calls?
2. Point to the instruction that passes `local` to `checksum`. Is it `mov` or `lea`, and why?

### Day 4 — Structs, pointers, callback tables (the IddCx pattern in miniature)

**Do**
1. `ex04_structs.c` defines `Device` with an embedded `Callbacks` struct of three function pointers, a linked list of `Monitor`, and a `device_pump` loop that calls `cb.on_frame` per monitor. This is deliberately the same *shape* as a driver registering callbacks and a framework calling them.
2. In Ghidra, open the **stripped** Windows `-O2` build (`make stripped`). Start from `main`. Reconstruct `Device` and `Monitor` in the Data Type Manager (right-click → New → Structure), apply them to the pointer parameters, and watch the decompiler turn `*(long *)(param_1 + 0x30)` into `param_1->cb.on_frame`.
3. Find the three callback assignments in `device_init` **without** reading the source: look for a function that stores three code addresses at consecutive offsets of a struct. That search pattern is exactly how you'll find `IDD_CX_CLIENT_CONFIG` being filled in the real driver.

**Learn**
- Field access is `[reg + offset]`; the offset is the field's offset. Ghidra shows `param_1 + 0x30`; you turn it into a name by defining the struct.
- Function pointer call: `call qword ptr [rax+0x38]` or `call rax` after `mov rax, [rcx+0x38]`. In the decompiler: `(*(code *)param_1->field)(...)`.
- Linked-list traversal: a `mov reg, [reg+0x18]` inside a loop whose exit is `test reg, reg; jz`.
- Alignment and padding: why `flags` (4 bytes) is followed by 4 bytes of nothing before an 8-byte pointer.

**Check questions**
1. What is `sizeof(Monitor)` on x64 and why? Which field offset proves the `next` pointer is at `0x18`?
2. In `device_pump`, which register holds `d` across the loop, and why did the compiler choose a callee-saved one?
3. Describe, in one sentence, how you'd search a stripped binary for "a function that fills a table of function pointers".

### Day 5 — Optimized code

**Do**
1. `ex05_opt.c`: a loop calling two `static` helpers and a `switch`. Compare `-O0` vs `-O2` on Windows.
2. In the `-O2` build, find: where `square` and `classify` went (inlined), the jump table for the `switch` (Ghidra shows it as `switchD_...`), the loop with `lea` arithmetic instead of `imul`.

**Learn**
- Inlining: small functions vanish into callers. Code you expect to see as a call is spread inline.
- `lea rax, [rax+rax*2]` is multiply by 3. `shl`/`sar` for powers of two. `imul` with a magic constant followed by shifts is division by a constant.
- Branch layout: the compiler often inverts conditions and moves the unlikely path out of line; `jcc` targets that jump *backwards* are loops.
- Jump tables: `switch` becomes `movsxd rax, [table + rcx*4]; add rax, base; jmp rax`. Ghidra usually recovers these; if a function ends abruptly after an indirect `jmp`, it didn't.
- Tail calls: `jmp other_function` instead of `call; ret`.

**Check questions**
1. In the `-O2` `run` loop, what does the compiler do with the `acc > 1000000` branch? Is it a `cmp`+`jcc` or something else?
2. How many `call` instructions remain inside `run` at `-O2`, and what are they?

### Day 6 — PE format: sections, imports, exports

**Do**
1. `make ex06` builds `ex06_hashi.dll` (two exports, imports `GetTickCount` and `OutputDebugStringA`) and `ex06_user.exe` (loads it with `LoadLibraryA`/`GetProcAddress`).
2. Run `x86_64-w64-mingw32-objdump -x build/ex06_hashi.dll | less` and find: the section table, the Export Table, the Import Table, and the entry point. Then open it in Ghidra and find the same things in the **Symbol Tree** (Exports, Imports) and **Memory Map**.
3. In Ghidra, open `hashi_tick`, find the `call qword ptr [rip+X]` that reaches `GetTickCount`. Follow it to the IAT entry. That is what every Windows API call looks like in a Release binary.

**Learn**
- Sections: `.text` code, `.rdata` constants + import/export directories, `.data` globals, `.pdata`/`.xdata` unwind data (every non-leaf x64 function has an entry here, which Ghidra uses to find functions), `.reloc`.
- Imports: the IAT is an array of pointers filled by the loader; `__imp_Foo` is the IAT slot; code calls `[__imp_Foo]`. A UMDF driver imports from `kernel32`, `ntdll`, `d3d11`/`dxgi` (for the swapchain), and possibly `ws2_32` or RPC libraries, which is why the imports list is the first thing you read.
- Exports: a UMDF driver usually exports nothing interesting; its entry comes from the WDF stub. Don't expect to find `EvtIddCx*` as exports.
- `DllMain` vs a driver's `DriverEntry`: in UMDF 2 the framework stub calls your `DriverEntry`; it's internal, not exported.

**Check questions**
1. Why does `hashi_tick` call `[rip+X]` rather than `call GetTickCount` directly?
2. Which section holds the string `"hashi dll attach\n"` and how did you find it in Ghidra?
3. What is in `.pdata`, and why does Ghidra care about it?

### Day 7 — Consolidation and the textbook

**Do**
1. Re-do Day 4 from scratch on the stripped `-O2` Windows build, timed. Goal: full struct recovery in under 45 minutes.
2. Read Microsoft's sample driver source (`Windows-driver-samples/video/IndirectDisplay/IddSampleDriver/Driver.cpp`, on GitHub) as *C++ to be understood*, not as a binary yet. Write down, in your own words: what `IddSampleDeviceAdd` fills into `IDD_CX_CLIENT_CONFIG`, what `SwapChainProcessor::RunCore` does per iteration, and which IddCx functions it calls (it uses `IddCxSwapChainSetDevice`, `IddCxSwapChainReleaseAndAcquireBuffer`, `IddCxSwapChainFinishedProcessingFrame`, and waits with a 16 ms timeout; verify this yourself).
3. Write a half-page "what I expect the compiled sample to look like" prediction. Week 3 tests it.

**Week 1 checkpoint (send me your answers)**
- The 17 check questions above.
- One paragraph: "How I would find the callback table in a stripped IddCx driver."

---

## 4. Week 2 outline — Windows flavor

- **MSVC idioms** by building the same C with Compiler Explorer's `x64 msvc v19.x /O2`: `__chkstk` for frames over 4 KiB, `__security_cookie`, `_RTC_*` in Debug builds, `__GSHandlerCheck`, C++ `__CxxFrameHandler4` and the `.xdata` EH tables, CRT init (`__scrt_*`). Goal: a cheat sheet of "safe to ignore" names.
- **C++ objects:** `this` in RCX; constructor fills a vtable pointer at offset 0 then fields; virtual call `mov rax,[rcx]; call [rax+0x10]`; `operator new`/`delete` imports; `std::unique_ptr`/`std::vector` inlined template noise; a lambda passed to `CreateThread` shows as a small function taking one `void*`. Exercise: compile a tiny class hierarchy with MinGW g++ and with MSVC on godbolt.
- **Windows API in disassembly:** `CreateEventW`, `CreateThread`, `WaitForMultipleObjects`, `CreateFileMappingW`/`MapViewOfFile`, `CreateNamedPipeW`, `DeviceIoControl`, `CoCreateInstance`, `RpcBindingFromStringBindingW`, `WSAStartup`. Exercise: write a 40-line program using three of these, build with MinGW, find each call in Ghidra, recover the argument values.
- **PE details:** load config, delay-load imports, resources (version info is where "LuminonCore WDDM PROXY" came from), Authenticode signature location (not executable code).
- **TryHackMe:** "Windows x64 Assembly" room first (25 min, listed as the first of the series), then "Windows Reversing Intro" (60 min, uses IDA Freeware in-room; do the same binaries in Ghidra afterwards so your Ghidra habits form).

## 5. Week 3 outline — WDF and IddCx patterns, build the sample

- **WDF in binaries:** every framework call is `call [WdfFunctions_02015 + 8*index]` with `WdfDriverGlobals` in RCX. The index-to-name map is `WDFFUNCENUM` in the WDK header `wdffuncenum.h` (UMDF 2.15 for this driver). Object contexts come from `WdfObjectGetTypedContextWorker`, which is itself a table call. `WDF_DRIVER_CONFIG` and `WDF_PNPPOWER_EVENT_CALLBACKS` are structs of function pointers filled before `WdfDriverCreate`/`WdfDeviceCreate`.
- **IddCx in binaries:** the DDI reference shows every `PFN_IDDCX*` function pointer type takes `PIDD_DRIVER_GLOBALS` as its first argument (Fact, from the `PFN_IDDCXREPORTCRITICALERROR` page). Inference: like WDF, IddCx calls are indirect through a per-driver function table with the globals pointer in RCX, and the table index order is defined in `iddcx.h`. Confirm the table's name and the enum once the WDK is installed. `IDD_CX_CLIENT_CONFIG` is a struct of callback pointers whose field order is in `iddcx.h`; `EvtIddCxMonitorAssignSwapChain` is at a fixed offset in it. **Finding the function that fills this struct and passes it to `IddCxDeviceInitConfig` locates every DDI callback in one step, no diffing needed.**
- **Build the sample in the Win11 VM** (a `win11` VM already exists in GNOME Boxes on this machine, last touched 2026-09-02). Install VS 2022 or VS 2026 (both are now supported by the WDK, see `driver-build-setup.md`), the SDK, the WDK. Build the sample twice: **Release with PDB** (closest in code shape to the vendor's shipped binary, still fully named) and Debug with PDB (easiest to read). Import both into Ghidra with their PDBs.
- **Exercise:** in the Release sample, without looking at source, find `IDD_CX_CLIENT_CONFIG` being filled, then `SwapChainProcessor::RunCore` and its 16 ms wait. Then confirm against the PDB names. This is the dress rehearsal for Week 4.

## 6. Week 4 outline — first look at `lci_iddcx.dll`

Strict checklist, in order; stop when something is unclear and write it up as Hypothesis:

1. `file`, size, section table, entropy of `.text` (rule out packing). Version resource. Signature present?
2. Imports inventory by DLL. Classify each import: WDF/IddCx table (framework), D3D/DXGI (frame access), threading/sync, IPC candidates (sections, pipes, sockets, RPC, COM), everything else.
3. Strings: unicode and ASCII. Device interface GUIDs, pipe or section names, registry paths, log format strings. These usually answer the IPC question before any code is read.
4. Locate the WDF function table global and the IddCx function table global. Name them. Now every framework call in the binary is readable.
5. Locate the `IDD_CX_CLIENT_CONFIG` fill. Name all callbacks from their offsets. Record whether `IDDCX_ADAPTER_FLAGS_REMOTE_SESSION_DRIVER` is set in the adapter caps (answers the console-vs-remote inference).
6. Read `AssignSwapChain` and the thread it starts. Record only behavior: what it calls, what it waits on, where the frame goes.
7. Only after 1–6: Ghidra Version Tracking against the sample for whatever is still unnamed.

Everything found goes in the devlog as Fact / Inference / Hypothesis with the evidence (import name, string, offset), never as copied code.

---

## 7. Cheat sheets

### Microsoft x64 calling convention

| Thing | Where |
|---|---|
| Integer/pointer args 1–4 | RCX, RDX, R8, R9 |
| Float/double args 1–4 | XMM0–XMM3 (slot by position, not by float count) |
| Args 5+ | Stack, `[rsp+0x28]`, `[rsp+0x30]`, ... at function entry (after the 0x20 shadow + 8 return address) |
| Return | RAX (integer/pointer), XMM0 (float/double); structs > 8 bytes via hidden pointer in RCX |
| `this` | RCX (so first real arg of a method is RDX) |
| Shadow space | 32 bytes reserved by caller, always |
| Alignment | RSP is 16-byte aligned before `call` |
| Callee-saved | RBX, RBP, RDI, RSI, R12–R15, XMM6–XMM15 |
| Volatile | RAX, RCX, RDX, R8–R11, XMM0–XMM5 |

### Prologue patterns you will see

```
sub rsp, 28h                    ; leaf-ish function: shadow + alignment, no saved regs
push rbx ; sub rsp, 20h         ; one callee-saved reg + shadow
mov [rsp+8], rcx ; push rdi ...  ; "home" the arg into shadow space, then save regs (common in MSVC)
push rbp ; mov rbp, rsp ; sub rsp, N   ; frame pointer kept (Debug builds, or functions using alloca/EH)
sub rsp, 1000h+ ... call __chkstk ; large frame: stack probe
```

### MSVC names that are safe to ignore

`__security_cookie`, `__security_check_cookie`, `__security_init_cookie`, `__chkstk`, `__GSHandlerCheck`, `__CxxFrameHandler4`, `__C_specific_handler`, `__scrt_*`, `_RTC_*`, `__std_terminate`, `_guard_dispatch_icall` (Control Flow Guard: an indirect call goes through this; the real target is in RAX).

### Ghidra habits

- Import with `File → Import File`, then say yes to analysis. For PE with PDB, put the `.pdb` next to the binary or configure the symbol server in `Edit → Tool Options → PDB`.
- `L` renames, `T` retypes, `;` adds a comment, `Ctrl-Shift-G` edits a function signature, `Ctrl-L` on a parameter retypes it.
- Data Type Manager → right-click your program's archive → New → Structure. Fill fields by offset. Apply with `T` on a pointer variable.
- Window → Function Call Trees for callers/callees. Window → Symbol Tree → Imports for the API inventory.
- Decompiler is wrong about a function when you see `in_RAX`, `unaff_RBX`, `extraout_*`: fix the signature or convention first.

---

## 8. Resources (official or primary where possible)

- Microsoft, "x64 calling convention" and "x64 stack usage" (learn.microsoft.com, C++ build reference). The authoritative spec for everything in the cheat sheet.
- Intel SDM Volume 1 chapter 3 (basic execution environment) and Volume 2 for individual instructions; or the AMD64 APM Volume 3. Use as a dictionary, don't read cover to cover.
- Compiler Explorer (godbolt.org): `x64 msvc v19.latest` and `x86-64 gcc` with `-O2` for instant side-by-side.
- Ghidra: the built-in help (F1) is good; the "Ghidra Cheat Sheet" at ghidra-sre.org.
- Microsoft, Windows-driver-samples `video/IndirectDisplay/IddSampleDriver/Driver.cpp` (the textbook for Week 3). Note: this sample was first published 2020-02-19, after the Splashtop driver's 2018-12 build date, so expect the vendor binary to differ more than "sample plus extra code".
- Microsoft, "IddCx versions", "Building IddCx 1.4 drivers", "IddCx objects" (learn.microsoft.com, display drivers).
- TryHackMe: "Windows x64 Assembly" (tryhackme.com/room/win64assembly) then "Windows Reversing Intro" (tryhackme.com/room/windowsreversingintro).
- Optional book: *The Ghidra Book* (Eagle & Nance) for tool depth; skip exploit-focused books for now.
