/* Day 1: registers, mov/lea/add/imul, cmp+jcc, call/ret.
 * Build: make  -> build/ex01_basics.{linux,win}-O{0,2}[.exe]
 * Read:  build/ex01_basics.s.linux-O0 first, then in Ghidra. */
#include <stdio.h>
#include <stdlib.h>

__attribute__((noinline)) int add3(int a, int b, int c)
{
    return a + b * c;
}

int main(int argc, char **argv)
{
    int x = argc > 1 ? atoi(argv[1]) : 7;
    int y = add3(x, 3, 4);
    if (y > 20)
        puts("big");
    else
        puts("small");
    return y & 0xff;
}
