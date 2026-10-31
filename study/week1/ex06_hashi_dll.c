/* Day 6 (Windows only): a DLL with two exports and two imports.
 * Inspect with: x86_64-w64-mingw32-objdump -x build/ex06_hashi.dll
 * Then in Ghidra: Symbol Tree -> Exports / Imports, follow the IAT thunk
 * from hashi_tick to GetTickCount. */
#include <windows.h>

__declspec(dllexport) int hashi_add(int a, int b)
{
    return a + b;
}

__declspec(dllexport) DWORD hashi_tick(void)
{
    return GetTickCount();
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved)
{
    (void)h; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH)
        OutputDebugStringA("hashi dll attach\n");
    return TRUE;
}
