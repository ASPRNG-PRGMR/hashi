# Week 1 exercises. Builds each C file four ways (Linux/Windows x -O0/-O2),
# plus Intel-syntax assembly listings and a stripped Windows build for Day 4.
#
#   make          all binaries with debug info into build/
#   make asm      build/*.s.<target> assembly listings
#   make stripped build/*.win-O2-stripped.exe (no symbols; practice target)
#   make ex06     the Day 6 DLL + user program (Windows only)
#   make run      run the Linux -O2 binaries once as a smoke test
#   make clean

CC_LINUX := gcc
CC_WIN   := x86_64-w64-mingw32-gcc
CFLAGS   := -g -Wall -Wextra -fno-omit-frame-pointer
# Keep it readable: no PIE-related indirection on Linux, no fancy vectorizing.
LFLAGS_LINUX := -no-pie -fno-pie
EXS := ex01_basics ex02_callconv ex03_frames ex04_structs ex05_opt
B := build

all: $(B) $(foreach e,$(EXS),$(B)/$(e).linux-O0 $(B)/$(e).linux-O2 $(B)/$(e).win-O0.exe $(B)/$(e).win-O2.exe)

$(B):
	mkdir -p $(B)

$(B)/%.linux-O0: %.c | $(B)
	$(CC_LINUX) $(CFLAGS) $(LFLAGS_LINUX) -O0 -o $@ $<
$(B)/%.linux-O2: %.c | $(B)
	$(CC_LINUX) $(CFLAGS) $(LFLAGS_LINUX) -O2 -o $@ $<
$(B)/%.win-O0.exe: %.c | $(B)
	$(CC_WIN) $(CFLAGS) -O0 -o $@ $<
$(B)/%.win-O2.exe: %.c | $(B)
	$(CC_WIN) $(CFLAGS) -Wno-cast-function-type -O2 -o $@ $<

asm: $(B) $(foreach e,$(EXS),$(B)/$(e).s.linux-O0 $(B)/$(e).s.linux-O2 $(B)/$(e).s.win-O0 $(B)/$(e).s.win-O2)
$(B)/%.s.linux-O0: %.c | $(B)
	$(CC_LINUX) $(CFLAGS) -O0 -S -masm=intel -fno-asynchronous-unwind-tables -o $@ $<
$(B)/%.s.linux-O2: %.c | $(B)
	$(CC_LINUX) $(CFLAGS) -O2 -S -masm=intel -fno-asynchronous-unwind-tables -o $@ $<
$(B)/%.s.win-O0: %.c | $(B)
	$(CC_WIN) $(CFLAGS) -O0 -S -masm=intel -o $@ $<
$(B)/%.s.win-O2: %.c | $(B)
	$(CC_WIN) $(CFLAGS) -O2 -S -masm=intel -o $@ $<

stripped: $(B) $(foreach e,$(EXS),$(B)/$(e).win-O2-stripped.exe)
$(B)/%.win-O2-stripped.exe: %.c | $(B)
	$(CC_WIN) -Wall -O2 -s -o $@ $<

ex06: $(B)/ex06_hashi.dll $(B)/ex06_user.exe
$(B)/ex06_hashi.dll: ex06_hashi_dll.c | $(B)
	$(CC_WIN) $(CFLAGS) -O2 -shared -o $@ $<
$(B)/ex06_user.exe: ex06_user.c | $(B)
	$(CC_WIN) $(CFLAGS) -Wno-cast-function-type -O2 -o $@ $<

run: all
	@for e in $(EXS); do echo "== $$e"; ./$(B)/$$e.linux-O2 || echo "exit=$$?"; done

clean:
	rm -rf $(B)

.PHONY: all asm stripped ex06 run clean
