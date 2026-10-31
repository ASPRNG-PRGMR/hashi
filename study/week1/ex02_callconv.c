/* Day 2: Microsoft x64 vs System V calling convention.
 * sum6: six integer args -> which go in registers, which on the stack?
 * mix:  interleaved int/double -> XMM slots are by position on Windows. */
#include <stdio.h>

__attribute__((noinline)) long sum6(long a, long b, long c, long d, long e, long f)
{
    return a + b + c + d + e + f;
}

__attribute__((noinline)) double mix(int i, double d, int j, double e)
{
    return i * d + j * e;
}

__attribute__((noinline)) void noargs(void)
{
    puts("noargs");          /* still needs 32 bytes of shadow space on Windows */
}

int main(void)
{
    noargs();
    printf("%ld %f\n", sum6(1, 2, 3, 4, 5, 6), mix(2, 1.5, 3, 2.5));
    return 0;
}
