/* Day 6 (Windows only): dynamic import via LoadLibrary/GetProcAddress.
 * Compare with the static IAT import inside the DLL itself. */
#include <windows.h>
#include <stdio.h>

typedef int (*add_fn)(int, int);
typedef DWORD (*tick_fn)(void);

int main(void)
{
    HMODULE m = LoadLibraryA("ex06_hashi.dll");
    if (!m) { printf("LoadLibrary failed: %lu\n", GetLastError()); return 1; }
    add_fn add = (add_fn)GetProcAddress(m, "hashi_add");
    tick_fn tick = (tick_fn)GetProcAddress(m, "hashi_tick");
    if (!add || !tick) { puts("GetProcAddress failed"); return 2; }
    printf("add=%d tick=%lu\n", add(2, 3), tick());
    FreeLibrary(m);
    return 0;
}
