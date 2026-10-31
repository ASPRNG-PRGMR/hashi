# Week 1 exercises

Companion to [`docs/study-plan-x64-windows-reversing.md`](../../docs/study-plan-x64-windows-reversing.md), section 3.

| File | Day | Teaches |
|---|---|---|
| `ex01_basics.c` | 1 | registers, `mov`/`lea`/`imul`, `cmp`+`jcc`, `call`/`ret` |
| `ex02_callconv.c` | 2 | Microsoft x64 vs System V argument passing, shadow space |
| `ex03_frames.c` | 3 | prologue/epilogue, frame size, locals, stack cookie |
| `ex04_structs.c` | 4 | struct field offsets, linked list, **table of function pointers** (the IddCx shape) |
| `ex05_opt.c` | 5 | `-O0` vs `-O2`: inlining, `lea` math, jump tables |
| `ex06_hashi_dll.c`, `ex06_user.c` | 6 | PE exports, IAT imports, `LoadLibrary`/`GetProcAddress` |

```
make            # all five exercises, Linux + Windows, -O0 + -O2, with debug info
make asm        # Intel-syntax .s listings next to the binaries
make stripped   # symbol-less Windows -O2 builds for the Day 4 / Day 7 drills
make ex06       # the DLL exercise (Windows binaries; run under Wine or in the VM)
make run        # smoke-test the Linux -O2 binaries
```

Windows binaries are built with MinGW-w64 on Fedora. They use the real Microsoft x64 calling convention and real PE format, so Ghidra treats them exactly like an MSVC build for the purposes of Week 1. Differences from MSVC (different prologue style, GCC's `__stack_chk_fail` instead of `__security_cookie`, DWARF instead of PDB) are covered in Week 2.

Ghidra reads the DWARF debug info MinGW embeds in the PE when you build with `-g`, so the non-stripped builds give you names much like a PDB would. Use the `stripped` builds when the exercise says "without symbols".
