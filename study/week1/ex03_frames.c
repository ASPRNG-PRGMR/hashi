/* Day 3: prologue/epilogue, frame size, locals, stack cookies.
 * `work` has a 64-byte buffer: find it in the frame; find the cookie check. */
#include <stdio.h>
#include <string.h>

__attribute__((noinline)) int checksum(const char *buf, int n)
{
    int s = 0;
    for (int i = 0; i < n; i++)
        s = s * 31 + buf[i];
    return s;
}

__attribute__((noinline)) int work(const char *name)
{
    char local[64];
    int len;
    strncpy(local, name, sizeof local - 1);
    local[sizeof local - 1] = 0;
    len = (int)strlen(local);
    return checksum(local, len);
}

int main(int argc, char **argv)
{
    return work(argc > 1 ? argv[1] : "hashi") & 0x7f;
}
