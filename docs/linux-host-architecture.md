# Linux host architecture on GNOME Wayland — FED-ARCH-E001

Written 2026-11-08 on the target machine. Environment facts below were read from
the running system, not assumed.

## Environment (Fact, measured)

| Item | Value |
| --- | --- |
| Session type | `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-0` |
| Compositor | GNOME Shell 51.1 / `mutter-51.1-1.fc45` |
| PipeWire | 1.6.11 |
| `gnome-remote-desktop` | 51.0-1.fc45 (present) |
| usbmuxd | service **active** |
| iPad on USB | `Bus 005 Device 009: ID 05ac:12ab Apple, Inc. iPad` |
| libimobiledevice CLI | **absent** — `idevice_id`, `ideviceinfo`, `idevicepair`, `iproxy` are all missing |

**Correction to an earlier note:** a previous session recorded
libimobiledevice/usbmuxd as "present". The usbmuxd *daemon* is running, but the
libimobiledevice *command-line tools* are not installed. That matters less than
it sounds — see the transport section.

## The decision: Mutter's virtual monitor, not a kernel module

The hard architectural question for HASHI was how a Linux host presents a display
the desktop can extend onto, then captures it. On GNOME Wayland the usual
candidates are poor fits: `Xvfb` is X11-only and cannot extend a Wayland desktop,
`VKMS` is awkward to expose alongside real GPUs, `wlroots` headless outputs do
not exist under Mutter, and `evdi` means an out-of-tree kernel module.

**Mutter already provides exactly what is needed, in userspace.**

**Fact — verified by reading the installed system, not from memory.**
`org.gnome.Mutter.ScreenCast` is present at version **4** and exposes
`CreateSession`. `org.gnome.Mutter.RemoteDesktop` is present at version **1**
with `SupportedDeviceTypes = 7`, i.e. the bitmask for keyboard, pointer **and
touchscreen**. The session-level methods are compiled into
`/usr/lib64/libmutter-51.so.0`; reading its strings confirms all of:

```text
RecordVirtual   RecordMonitor   RecordWindow   RecordArea
NotifyPointerMotionAbsolute     NotifyPointerButton
NotifyTouchDown  NotifyTouchMotion  NotifyTouchUp
NotifyKeyboardKeycode           ConnectToEIS
```

`RecordVirtual` is the one that matters: it creates a **virtual monitor** that
Mutter treats as a real output — so the desktop genuinely extends onto it — and
streams its contents over PipeWire.

## Why this maps onto the decoded protocol so cleanly

Every Windows-side mechanism established in FED-MODE/START/STREAM-E001 has a
direct GNOME counterpart:

| Windows agent (decoded) | Linux host (GNOME Wayland) |
| --- | --- |
| IddCx virtual display (LuminonCore `LCI\IDDCX`) | `ScreenCast.Session.RecordVirtual` virtual monitor |
| LCI captor → shared `+0x1c`/`+0x20` output dimensions | PipeWire stream from that virtual monitor |
| `SendInput` with `MOUSEEVENTF_*` button flags | `NotifyPointerButton` |
| `SendInput` positioned move, `0xC001` | `NotifyPointerMotionAbsolute` |
| `InjectTouchInput` with `ContactID` | `NotifyTouchDown`/`Motion`/`Up` with a slot |
| `SendInput` `KEYBDINPUT` `wVk`/`wScan` | `NotifyKeyboardKeycode` |

**Fact as of FED-DBUS-E001 — originally an Inference, now confirmed from
Mutter's implementation rather than from the method name.** The whole transform
for a virtual stream is `*x = stream_x + view_layout.x` (likewise for y): a pure
translation by the monitor's stage position, with no scaling and no
normalisation. `NotifyPointerMotionAbsolute` takes
coordinates relative to a **stream**, not to the whole desktop. The decoded
inbound coordinates are monitor-relative pixels, which is exactly what a
stream-relative call wants. So the virtual-desktop normalisation the Windows
agent performs — `((value + monitor_origin - desktop_origin) / desktop_span) *
65535` — has **no Linux equivalent to reproduce**. The iPad's coordinates go
straight in. That removes a whole class of placement bug.

**Inference:** multi-touch also lines up. The decoded `ContactID` is per-contact,
and Mutter's touch notifies are per-slot, so the mapping is a direct one.

## Consequences for the design

1. **No kernel module, no root, no out-of-tree driver.** The host is an ordinary
   user-session process speaking D-Bus and PipeWire.
2. **The capture side is PipeWire, not a framebuffer grab.** Frames arrive as
   buffers from the stream, which is also where DMA-BUF/zero-copy would come in
   if encoding throughput ever matters.
3. **Target size 1280×960** — the user's stated requirement, and the size all
   1,903 captured frames declare.
4. **Input flows the opposite way from the display.** The virtual monitor is a
   `ScreenCast` session; input injection is a separate `RemoteDesktop` session.
   A host needs both, and `RemoteDesktop` is the one that owns the stream
   association used by the absolute-motion call.

## Limitations and what is not yet verified

- **Fact vs design.** That the methods exist is verified. That they compose into
  a working HASHI host is a **design inference**, not a demonstrated result. No
  session has been created on this machine.
- ~~The exact parameter contracts of `RecordVirtual` and the `Notify*` calls were
  **not** verified.~~ **Closed 2026-11-08 as FED-DBUS-E001** — every signature is
  now verified three ways against the installed 51.1 build (live introspection,
  the library's own `GDBusMethodInfo` tables, and the unpatched Fedora source
  RPM). See [Mutter D-Bus contracts](fedora-mutter-dbus-contracts.md). Two
  results change the design: `RecordVirtual` accepts a **`modes`** key that pins
  the virtual monitor to exactly 1280×960 and makes the PipeWire stream
  non-resizable, and `NotifyPointerButton`'s `button` argument is an **evdev**
  code (`BTN_LEFT` = 272), not a Win32 flag or a Clutter button number.
- These are Mutter's **private** D-Bus APIs, the ones `gnome-remote-desktop`
  uses, not the portal. They are not a stable public contract and can change
  between GNOME releases. A host pinned to them is pinned to a GNOME version
  range. The XDG desktop portal (`org.freedesktop.portal.ScreenCast` /
  `RemoteDesktop`) is the stable alternative, at the cost of a user permission
  prompt per session and, historically, no virtual-monitor support.
- Creating a `RemoteDesktop` or `ScreenCast` session has user-visible effects —
  a screen-sharing indicator at minimum. Nothing in this repository creates one.
- `ConnectToEIS` suggests a libei path exists alongside the `Notify*` calls.
  Unexamined; it may be the better long-term input route.

## Transport: usbmuxd without libimobiledevice

**Fact:** the usbmuxd daemon is active and the iPad is enumerated on USB, but the
libimobiledevice CLI tools are absent. This is not a blocker. The Windows capture
already contains the **complete usbmux control exchange** — 592 outgoing and 294
incoming bytes in the generation-3 streams, carrying `ListDevices` and `Connect`
plists, with the `Connect` port byte-swapped by `htons` as WIN-START-E005
recorded.

**Inference:** a host can therefore speak the usbmux protocol directly over the
daemon's local socket and be validated **offline against those captured bytes**,
the same way the handshake and image stream already are. That is a better test
than any amount of CLI tooling, and it keeps the dependency surface small.

**Not done, and deliberately so.** Opening a connection to the iPad's Splashtop
port is the Fedora-side replay the user previously declined. Enumerating devices
through the local daemon does not touch the iPad's application port, but sending
the handshake does. That step needs explicit confirmation and is not taken here.
