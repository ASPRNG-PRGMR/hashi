# Mutter 51 D-Bus contracts, verified — FED-DBUS-E001

2026-11-08. [Linux host architecture](linux-host-architecture.md) recorded the
`ScreenCast` and `RemoteDesktop` **method names** read out of the installed
library, and explicitly flagged that *"the exact parameter contracts of
`RecordVirtual` and the `Notify*` calls were **not** verified"* and *"must be
checked against Mutter 51's own interface definitions before code depends on
them."*

This report closes that gap. Every signature below is now verified against the
installed build. **No D-Bus session of any kind was created.** Introspection
reads an interface; it does not start a screen cast, and nothing here produced a
screen-sharing indicator.

Private evidence: run `fedora-dbus-20261108T042538Z`, file index SHA-256
`57d954b908f06dbeb04fac047c7ddd6cf0a97ad06091190fbdac65dd147b8c84`.

## Provenance

| Item | Value |
| --- | --- |
| Compositor | `mutter-51.1-1.fc45.x86_64`, `gnome-shell-51.1-1.fc45` |
| Library read | `/usr/lib64/libmutter-51.so.0`, SHA-256 `e5b3257490f181e873d4072bee73025e607e781dfc625f8e3d7c844db45e290f` |
| Source RPM | `mutter-51.1-1.fc45.src.rpm`, SHA-256 `f2a4a09d3aa7516706dad73ec6f8bfd35864f57d4d65d37e6464ba549f57c4ff` |
| Upstream tarball | `mutter-51.1.tar.xz`, SHA-256 `0d311d87901dbcb94518fb89304febe30852ce5d8a4befa9f87e85c68eceefde` |
| `ScreenCast` API version | 4 |
| `RemoteDesktop` API version | 1, `SupportedDeviceTypes = 7` |

**Fact — the source matches the installed binary.** `mutter.spec` applies
`%autosetup -S git` with **no** `Patch:` directives, so Fedora ships upstream
51.1 unpatched. The interface definitions quoted here are therefore the
contracts the running compositor actually implements, not upstream `main`, which
is a different and possibly diverged tree.

Three independent sources agree, which is why these are Facts and not
Inferences:

1. **Live introspection** of `/org/gnome/Mutter/ScreenCast` and
   `/org/gnome/Mutter/RemoteDesktop` (`gdbus introspect`) — top-level interfaces
   only, because the session and stream objects do not exist until a session is
   created.
2. **The installed library's own `GDBusMethodInfo`/`SignalInfo`/`PropertyInfo`
   tables**, recovered from `libmutter-51.so.0` by walking the ELF's relocated
   pointers. This covers the session-level methods that introspection cannot
   reach, and reflects the compiled binary rather than any source tree.
3. **The source RPM's `data/dbus-interfaces/*.xml`** plus the C implementations,
   which supply the documentation comments — in particular the `a{sv}` dictionary
   keys, which no introspection data contains.

A note on method: GNOME's GitLab now fronts raw files with an anti-bot
challenge, so upstream fetches failed. Using Fedora's source RPM for the exact
installed version is the better evidence anyway.

## Verified signatures

**Fact.** Extracted from the installed library and byte-for-byte consistent with
the shipped XML.

```text
org.gnome.Mutter.ScreenCast                     (Version = 4)
  CreateSession(in a{sv} properties, out o session_path)

org.gnome.Mutter.ScreenCast.Session
  Start()
  Stop()
  RecordVirtual(in a{sv} properties, out o stream_path)
  RecordMonitor(in s connector, in a{sv} properties, out o stream_path)
  RecordWindow(in a{sv} properties, out o stream_path)
  RecordArea(in i x, in i y, in i width, in i height,
             in a{sv} properties, out o stream_path)
  signal Closed()

org.gnome.Mutter.ScreenCast.Stream
  Start()
  Stop()
  signal PipeWireStreamAdded(u node_id)
  property Parameters : a{sv}  (read)

org.gnome.Mutter.RemoteDesktop                  (Version = 1,
                                                 SupportedDeviceTypes = 7)
  CreateSession(out o session_path)

org.gnome.Mutter.RemoteDesktop.Session
  Start()
  Stop()
  property SessionId : s  (read)
  signal Closed()
  NotifyPointerMotionAbsolute(in s stream, in d x, in d y)
  NotifyPointerMotionRelative(in d dx, in d dy)
  NotifyPointerButton(in i button, in b state)
  NotifyPointerAxis(in d dx, in d dy, in u flags)
  NotifyPointerAxisDiscrete(in u axis, in i steps)
  NotifyTouchDown(in s stream, in u slot, in d x, in d y)
  NotifyTouchMotion(in s stream, in u slot, in d x, in d y)
  NotifyTouchUp(in u slot)
  NotifyKeyboardKeycode(in u keycode, in b state)
  NotifyKeyboardKeysym(in u keysym, in b state)
  ConnectToEIS(in a{sv} options, out h fd)
```

**Correction to an earlier assumption.** `RemoteDesktop.CreateSession` takes **no
arguments** — only `ScreenCast.CreateSession` takes a properties dictionary. Two
`Start` and two `ConnectToEIS` arities appear in the extraction because the
library also contains unrelated interfaces; the `Session` ones are the zero-arg
`Start()` and, per the shipped XML, `ConnectToEIS(in a{sv} options, out h fd)`.

`Closed` is a zero-argument signal on both session interfaces, taken from the
XML; the struct walk cannot distinguish an empty argument list from a missing
one, so that detail rests on the XML alone (still a Fact, just a single source).

## The sizing question, settled — and in HASHI's favour

This was the open design risk: nothing was known about how a virtual monitor
acquires its resolution, and HASHI needs exactly 1280×960.

**Fact — `RecordVirtual` accepts a `modes` key that pins the size.** From
`data/dbus-interfaces/org.gnome.Mutter.ScreenCast.xml`, documenting
`RecordVirtual`:

```text
* "modes" (aa{sv}): List of modes to use. If set, the PipeWire stream
                    becomes non-resizable, and size is controlled by
                    the compositor as if it was a regular monitor.
Available mode properties:
* "size" ((uu)): Width and height. Required.
* "refresh-rate" (d): Refresh rate. Optional.
* "is-preferred" (b): Is the preferred mode.
Exactly one mode must be marked as "is-preferred".
```

The other accepted `RecordVirtual` keys are `cursor-mode` (u; 0 hidden,
1 embedded, 2 metadata; default hidden) and `is-platform` (b; default false —
when true the output "will not be interpreted as if the screen is shared, but
more transparently as if it was a real monitor").

**Fact — there are two distinct sizing paths, confirmed in the C source.**
`src/backends/meta-stream-source-virtual.c`:

- **With `modes`** — the monitor is created up front in
  `meta_stream_source_virtual_initable_init` from the supplied mode list;
  `meta_stream_source_virtual_get_specs` returns that mode's width, height and
  refresh rate, so the PipeWire stream advertises a **fixed** size; and
  `notify_params_updated` begins `if (source_virtual->mode_infos) return;`, so
  format negotiation can no longer resize the monitor.
- **Without `modes`** — `get_specs` returns `FALSE`, the stream is resizable, and
  `notify_params_updated` → `ensure_virtual_monitor(video_format)` creates (or
  resizes) the monitor to whatever size the *consumer* negotiated, by way of
  `create_mode_info`, which reads `video_format->size` and
  `max_framerate`.

**This corrects a hypothesis.** Before reading the source I had inferred from
`meta_virtual_monitor_info_new_inactive` and the error string "Failed to create
virtual monitor with size %dx%d" that the size *must* be negotiated through the
PipeWire format. That is real, but it is the **fallback** path, not the only one.
A client can pin an exact mode, which is strictly better for HASHI.

**Inference — HASHI should pass `modes` explicitly:**

```text
modes = [ { "size": (1280, 960), "refresh-rate": 30.0, "is-preferred": true } ]
```

A pinned mode makes the virtual monitor behave like a real 1280×960 output and
removes any possibility of the compositor or a negotiation quirk handing back a
different frame size — which matters because the protocol's 623-byte JPEG
prelude hard-codes 1280×960 and every emitted frame must match it. Validation
also becomes trivial: a captured buffer that is not 1280×960 is a bug, not a
case to handle.

`refresh-rate` defaults to `60.0` when omitted. `create_mode_infos` also accepts
an undocumented `preferred-scale` (d); HASHI should **not** set it (see the scale
caveat below). Rejections to expect: "Missing mode dimension", "Invalid mode
%dx%d" for a zero dimension, "Multiple preferred modes", "No preferred modes".

## Input coordinates: the simplification is confirmed as Fact

[Linux host architecture](linux-host-architecture.md) *inferred* that the
Windows virtual-desktop normalisation has no Linux equivalent. That is now
**Fact**, from the implementation rather than from the method name.

`handle_notify_pointer_motion_absolute` in
`src/backends/meta-remote-desktop-session.c` resolves the `stream` string to a
stream object and calls `meta_stream_transform_position (stream, x, y, &abs_x,
&abs_y)`. For a virtual stream
(`meta_stream_virtual_transform_position`, `src/backends/meta-stream-virtual.c`)
the whole transform is:

```c
clutter_stage_view_get_layout (view, &view_layout);
*x = stream_x + view_layout.x;
*y = stream_y + view_layout.y;
```

**A pure translation by the virtual monitor's position in the stage.** No
scaling, no normalisation, no 65535 constant. So the incoming `x`/`y` are
**stream-relative pixels measured from the stream's own top-left origin** — which
is exactly what FED-LIVE-E001 observed arriving from the iPad (x 3..1236,
y 2..951 inside a 1280×960 space). The iPad's coordinates go straight into the
call as doubles. The host never needs to know where the virtual monitor sits in
the desktop; Mutter adds that offset itself.

**Fact — `NotifyPointerButton`'s `button` is an evdev code.** The XML does not
say so, but the implementation does:

```c
button = meta_evdev_button_to_clutter (button_code);
```

So the argument is `BTN_LEFT` = `0x110` = **272**, not a Win32 `MOUSEEVENTF_*`
flag and not a Clutter 1/2/3 button number. The decoded Windows constants
(`field0` 5/6 ⇒ `MOUSEEVENTF_LEFTDOWN`/`LEFTUP`) must therefore be mapped onto
evdev codes, not passed through. `NotifyKeyboardKeycode`'s `keycode` is likewise
documented in the XML as "an evdev keycode".

**Fact — early input is silently dropped.** `transform_position` returns `FALSE`
unless the stream source is enabled *and* has a `ClutterStageView`, and the
caller then logs "Dropping early absolute pointer motion" and returns success
anyway. **A host must not treat a successful D-Bus return as proof that an event
was delivered**, and must not start injecting until the stream is genuinely
running.

## Session composition and ordering

**Fact.** `ScreenCast.CreateSession`'s documented properties are
`remote-desktop-session-id` (s) — "The ID of a remote desktop session. Remote
desktop driven screen casts are started and stopped by the remote desktop
session" — and `disable-animations` (b). `RemoteDesktop.Session` exposes
`SessionId` (s), "used to associate screen cast sessions with a remote desktop
session".

**Inference — the required order for HASHI** (each step's signature verified
above; the sequence itself is not yet demonstrated):

1. `RemoteDesktop.CreateSession()` → session path; read its `SessionId`.
2. `ScreenCast.CreateSession({"remote-desktop-session-id": <SessionId>})`.
3. `ScreenCast.Session.RecordVirtual({"modes": [...], "cursor-mode": 1})` →
   stream path. Cursor mode `1` (embedded) is the sensible choice: the iPad gets
   a visible cursor baked into the frames, and HASHI has no other way to draw one.
4. Subscribe to `Stream.PipeWireStreamAdded` **before** starting.
5. `RemoteDesktop.Session.Start()` — which starts the screen cast too, since a
   remote-desktop-driven cast is started by the remote desktop session.
6. Take `node_id` from the signal; connect `pipewiresrc path=<node_id>`.
7. Inject input with the **stream object path** from step 3 as the `stream`
   argument.

**Fact:** `Stream.Parameters` carries `position` (ii) and `size` (ii) in
compositor coordinates, so a host can read back where its monitor landed and how
big it is — useful as an assertion that the pinned mode took effect.

## Capture path

**Fact:** `pipewiresrc` is present and instantiable —
`/usr/lib64/gstreamer-1.0/libgstpipewire.so`, version 1.6.11, rank primary+1,
with both `path` and `fd` properties. It ships in the `pipewire` package itself;
`gstreamer1-plugin-pipewire` is **not** installed and is not needed. PyGObject
3.58.1 instantiates it.

So `pipewire-devel`'s absence does not block capture: frames can come through
GStreamer rather than libpipewire bindings, and the `node_id` from
`PipeWireStreamAdded` is what `pipewiresrc path=` wants.

## Limitations

- **Nothing here has been executed against a live session.** All of it is
  signature and source verification. That the calls compose into a working host
  remains a design Inference until a session is actually created — which has
  user-visible effects and needs the user's agreement first.
- **These are Mutter's private D-Bus APIs**, as the XML itself states: *"This API
  is private and not intended to be used outside of the integrated system that
  uses libmutter. No compatibility between versions are promised."* A host built
  on them is pinned to a GNOME version range, and this verification is valid for
  **51.1** only. `ScreenCast` is already at version 4; the `modes` key is version
  3+ for `is-platform` and undated for `modes` itself, so earlier GNOME releases
  may lack it.
- **The scale caveat.** `transform_position` is a pure translation, which means
  Mutter treats the incoming coordinates as **logical** stage pixels. If the
  virtual monitor ends up with a scale other than 1, logical coordinates and
  PipeWire buffer pixels diverge, and the 1:1 pass-through above would be wrong.
  HASHI leaves `preferred-scale` unset, so Mutter chooses; a host should assert
  that the captured buffer is 1280×960 and that `Stream.Parameters` reports
  `size = (1280, 960)` rather than assume it.
- `ConnectToEIS`/libei is verified to exist but remains unexamined; it may be the
  better long-term input route than the `Notify*` calls.
- `Closed` signal arity rests on the XML alone, as noted above.
- No vendor code is involved in any of this. Mutter is the host platform's own
  GPL-licensed compositor and these are its published interface definitions,
  the same standing as the Microsoft API documentation used on the Windows side.
