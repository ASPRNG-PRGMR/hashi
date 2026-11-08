"""GNOME/Mutter virtual monitor and input injection for the HASHI Linux host.

This module is the Linux-side counterpart of the decoded Windows agent: it
creates a **virtual monitor** the GNOME desktop genuinely extends onto, captures
it over PipeWire, and injects the iPad's input back into the session.

Every D-Bus signature used here is verified against the installed Mutter build
as **FED-DBUS-E001** (`docs/fedora-mutter-dbus-contracts.md`), three ways: live
introspection, the ``GDBusMethodInfo`` tables inside ``libmutter-51.so.0``, and
the unpatched ``mutter-51.1-1.fc45`` source RPM. Nothing here is guessed.

Two cautions that the verification turned up, and that the code below encodes:

* **These are Mutter's private D-Bus APIs.** The interface XML states outright
  that no compatibility between versions is promised. :data:`VERIFIED_VERSIONS`
  records what was actually checked, and :func:`check_versions` refuses to
  assume anything else.
* **Creating a session has user-visible effects** — a screen-sharing indicator
  at minimum, and a new monitor appearing on the desktop. Importing this module
  does nothing at all; :class:`VirtualDisplaySession` touches the bus only when
  its methods are called.

The pure planning functions (properties dictionaries, the injection plan) carry
no I/O and are validated offline against FED-LIVE-E001's observed records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "GnomeError",
    "SCREEN_CAST_BUS_NAME",
    "SCREEN_CAST_OBJECT_PATH",
    "SCREEN_CAST_IFACE",
    "SCREEN_CAST_SESSION_IFACE",
    "SCREEN_CAST_STREAM_IFACE",
    "REMOTE_DESKTOP_BUS_NAME",
    "REMOTE_DESKTOP_OBJECT_PATH",
    "REMOTE_DESKTOP_IFACE",
    "REMOTE_DESKTOP_SESSION_IFACE",
    "VERIFIED_VERSIONS",
    "CURSOR_MODE_HIDDEN",
    "CURSOR_MODE_EMBEDDED",
    "CURSOR_MODE_METADATA",
    "BTN_LEFT",
    "BTN_RIGHT",
    "BTN_MIDDLE",
    "EVDEV_BUTTON_FOR_FIELD0",
    "DEVICE_TYPE_KEYBOARD",
    "DEVICE_TYPE_POINTER",
    "DEVICE_TYPE_TOUCHSCREEN",
    "check_versions",
    "supports_device_types",
    "virtual_monitor_mode",
    "record_virtual_properties",
    "screen_cast_session_properties",
    "to_glib_variant_dict",
    "InjectionCall",
    "plan_injection",
    "VirtualDisplaySession",
]

# Target size. FED-MODE-E001 settled this: it is the user's own chosen mode and
# the size all 1,903 captured frames declare. hashi_jpeg's 623-byte prelude
# hard-codes it, so a captured buffer of any other size is a bug.
TARGET_WIDTH = 1280
TARGET_HEIGHT = 960

#: Frames per second. hashi_stream paces off ``1000 / fps``.
TARGET_REFRESH = 30.0


class GnomeError(RuntimeError):
    """A Mutter D-Bus contract was violated, or the environment is unsupported."""


# ---------------------------------------------------------------------------
# Verified contract surface — FED-DBUS-E001
# ---------------------------------------------------------------------------

SCREEN_CAST_BUS_NAME = "org.gnome.Mutter.ScreenCast"
SCREEN_CAST_OBJECT_PATH = "/org/gnome/Mutter/ScreenCast"
SCREEN_CAST_IFACE = "org.gnome.Mutter.ScreenCast"
SCREEN_CAST_SESSION_IFACE = "org.gnome.Mutter.ScreenCast.Session"
SCREEN_CAST_STREAM_IFACE = "org.gnome.Mutter.ScreenCast.Stream"

REMOTE_DESKTOP_BUS_NAME = "org.gnome.Mutter.RemoteDesktop"
REMOTE_DESKTOP_OBJECT_PATH = "/org/gnome/Mutter/RemoteDesktop"
REMOTE_DESKTOP_IFACE = "org.gnome.Mutter.RemoteDesktop"
REMOTE_DESKTOP_SESSION_IFACE = "org.gnome.Mutter.RemoteDesktop.Session"

#: The API versions FED-DBUS-E001 actually verified, on mutter-51.1-1.fc45.
#:
#: **Fact.** ``ScreenCast.Version = 4`` and ``RemoteDesktop.Version = 1``, read
#: by live introspection. The ``modes`` key this module depends on is not
#: version-tagged in the XML, unlike ``is-platform`` ("since version 3"), so a
#: lower ScreenCast version is not safe to assume compatible.
VERIFIED_VERSIONS = {"ScreenCast": 4, "RemoteDesktop": 1}

#: ``cursor-mode`` values, documented in the RecordMonitor doc comment.
CURSOR_MODE_HIDDEN = 0
CURSOR_MODE_EMBEDDED = 1
CURSOR_MODE_METADATA = 2

#: ``SupportedDeviceTypes`` bits. The installed build reports 7 = all three.
DEVICE_TYPE_KEYBOARD = 1
DEVICE_TYPE_POINTER = 2
DEVICE_TYPE_TOUCHSCREEN = 4


def check_versions(screen_cast_version: int, remote_desktop_version: int) -> None:
    """Refuse to drive a Mutter whose API versions were never verified.

    These are private APIs with no compatibility promise, so a mismatch is a
    reason to stop rather than to hope. A *higher* ScreenCast version is also
    rejected: Mutter could have changed the ``modes`` contract, and this host
    would have no way to notice except by producing wrong-sized frames.
    """
    if screen_cast_version != VERIFIED_VERSIONS["ScreenCast"]:
        raise GnomeError(
            f"ScreenCast API version {screen_cast_version} was never verified; "
            f"FED-DBUS-E001 checked version {VERIFIED_VERSIONS['ScreenCast']} "
            "on mutter-51.1. These are private APIs with no compatibility "
            "promise — re-verify the contracts before proceeding."
        )
    if remote_desktop_version != VERIFIED_VERSIONS["RemoteDesktop"]:
        raise GnomeError(
            f"RemoteDesktop API version {remote_desktop_version} was never "
            f"verified; FED-DBUS-E001 checked version "
            f"{VERIFIED_VERSIONS['RemoteDesktop']} on mutter-51.1."
        )


def supports_device_types(supported: int, required: int) -> bool:
    """Whether a ``SupportedDeviceTypes`` bitmask covers everything required."""
    return supported & required == required


# ---------------------------------------------------------------------------
# RecordVirtual properties — the pinned-mode path
# ---------------------------------------------------------------------------
#
# **Fact (FED-DBUS-E001).** The ScreenCast XML documents, for RecordVirtual:
#
#     * "modes" (aa{sv}): List of modes to use. If set, the PipeWire stream
#                         becomes non-resizable, and size is controlled by
#                         the compositor as if it was a regular monitor.
#     * "size" ((uu)): Width and height. Required.
#     * "refresh-rate" (d): Refresh rate. Optional.
#     * "is-preferred" (b): Is the preferred mode.
#     Exactly one mode must be marked as "is-preferred".
#
# and ``create_mode_infos`` in ``src/backends/meta-screen-cast-session.c``
# enforces exactly that, rejecting a missing ``size``, a zero dimension,
# multiple preferred modes and no preferred mode.
#
# **Why HASHI pins the mode rather than negotiating.** Without ``modes``,
# ``meta_stream_source_virtual_get_specs`` returns FALSE, the stream is
# resizable, and the monitor is created at whatever size the *consumer*
# negotiates. With ``modes``, the monitor is created up front in
# ``meta_stream_source_virtual_initable_init`` and ``notify_params_updated``
# returns early, so negotiation cannot resize it. The protocol's JPEG prelude
# hard-codes 1280x960, so a fixed mode turns a whole class of size mismatch
# into an impossibility.


def virtual_monitor_mode(
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    refresh_rate: float | None = TARGET_REFRESH,
    *,
    is_preferred: bool = True,
) -> dict[str, tuple[str, object]]:
    """One entry of ``RecordVirtual``'s ``modes`` array.

    Returned as ``{key: (signature, value)}`` so the structure can be checked
    without GLib; :func:`to_glib_variant_dict` does the conversion.

    ``refresh_rate`` of None omits the key, which makes Mutter default it to
    60.0 (``create_mode_infos``). Mutter validates the rest, but a dimension of
    zero is rejected here too, so the failure names the caller's mistake rather
    than arriving as a D-Bus error string.
    """
    if width <= 0 or height <= 0:
        raise GnomeError(
            f"mode {width}x{height} has a non-positive dimension; Mutter "
            "rejects these as 'Invalid mode'"
        )
    mode: dict[str, tuple[str, object]] = {"size": ("(uu)", (width, height))}
    if refresh_rate is not None:
        if refresh_rate <= 0:
            raise GnomeError(f"refresh rate must be positive, got {refresh_rate}")
        mode["refresh-rate"] = ("d", float(refresh_rate))
    mode["is-preferred"] = ("b", bool(is_preferred))
    return mode


def record_virtual_properties(
    modes: list[dict[str, tuple[str, object]]] | None = None,
    *,
    cursor_mode: int = CURSOR_MODE_EMBEDDED,
    is_platform: bool | None = None,
) -> dict[str, tuple[str, object]]:
    """The ``properties`` dictionary for ``Session.RecordVirtual``.

    Defaults to a single pinned 1280x960 at 30 Hz with an **embedded** cursor.

    *Embedded* is the right default for HASHI, not Mutter's own default of
    hidden: the cursor is composited into the frames, which is the only way the
    iPad can show one — the protocol has no cursor channel, and the device is
    rendering a remote desktop, not driving a local pointer.

    ``is_platform`` is left unset by default. Setting it true asks Mutter to
    treat the output "more transparently as if it was a real monitor" rather
    than as a shared screen, which is closer to what HASHI is, but it also
    suppresses the sharing indicator — so it stays an explicit decision for the
    user to make, not a default this module takes on their behalf.
    """
    if cursor_mode not in (
        CURSOR_MODE_HIDDEN,
        CURSOR_MODE_EMBEDDED,
        CURSOR_MODE_METADATA,
    ):
        raise GnomeError(
            f"unknown cursor mode {cursor_mode}; Mutter accepts 0, 1 or 2"
        )
    if modes is None:
        modes = [virtual_monitor_mode()]
    if not modes:
        raise GnomeError("modes must not be empty; Mutter rejects 'No preferred modes'")

    preferred = [m for m in modes if m.get("is-preferred", ("b", False))[1]]
    if len(preferred) != 1:
        raise GnomeError(
            f"exactly one mode must be preferred, got {len(preferred)}; Mutter "
            "rejects 'Multiple preferred modes' and 'No preferred modes'"
        )

    properties: dict[str, tuple[str, object]] = {
        "modes": ("aa{sv}", modes),
        "cursor-mode": ("u", cursor_mode),
    }
    if is_platform is not None:
        properties["is-platform"] = ("b", bool(is_platform))
    return properties


def screen_cast_session_properties(
    remote_desktop_session_id: str | None = None,
    *,
    disable_animations: bool | None = None,
) -> dict[str, tuple[str, object]]:
    """The ``properties`` dictionary for ``ScreenCast.CreateSession``.

    **Fact (FED-DBUS-E001).** The XML documents exactly two keys:
    ``remote-desktop-session-id`` (s) — "The ID of a remote desktop session.
    Remote desktop driven screen casts are started and stopped by the remote
    desktop session" — and ``disable-animations`` (b).

    Passing the id is what binds the two sessions, and it is what makes
    ``NotifyPointerMotionAbsolute``'s ``stream`` argument resolvable: the
    handler fails with "No screen cast active" unless the remote-desktop
    session has a screen cast attached.
    """
    properties: dict[str, tuple[str, object]] = {}
    if remote_desktop_session_id is not None:
        if not remote_desktop_session_id:
            raise GnomeError("remote desktop session id must not be empty")
        properties["remote-desktop-session-id"] = ("s", remote_desktop_session_id)
    if disable_animations is not None:
        properties["disable-animations"] = ("b", bool(disable_animations))
    return properties


def to_glib_variant_dict(properties: dict[str, tuple[str, object]]):
    """Convert a ``{key: (signature, value)}`` mapping into a GLib ``a{sv}``.

    Imported lazily so this module stays importable, and most of it testable,
    without PyGObject.
    """
    from gi.repository import GLib  # noqa: PLC0415  (deliberately lazy)

    def pack(signature: str, value: object):
        if signature == "aa{sv}":
            return GLib.Variant(
                "aa{sv}",
                [
                    {k: pack(sig, val) for k, (sig, val) in entry.items()}
                    for entry in value  # type: ignore[union-attr]
                ],
            )
        return GLib.Variant(signature, value)

    return GLib.Variant(
        "a{sv}", {key: pack(sig, val) for key, (sig, val) in properties.items()}
    )


# ---------------------------------------------------------------------------
# Input injection — mapping the decoded TLV input channel onto RemoteDesktop
# ---------------------------------------------------------------------------
#
# Published Linux UAPI values from <linux/input-event-codes.h>, restated so the
# mapping below can be checked against them.
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112

#: ``field0`` -> the evdev button code to pass to ``NotifyPointerButton``.
#:
#: **Fact (FED-DBUS-E001):** the argument is an evdev code, not a Win32 flag and
#: not a Clutter button number. ``handle_notify_pointer_button`` converts it
#: with ``meta_evdev_button_to_clutter (button_code)``. The XML does not say so;
#: the implementation does.
#:
#: **Fact:** 5 and 6 are left down and up — statically decoded from the
#: MOUSEEVENTF_LEFTDOWN/LEFTUP constants the agent writes, and **observed live**
#: (FED-LIVE-E001: 41 downs, 40 ups, strictly alternating).
#:
#: **Static only, never observed on the wire:** 8/9 (right) and 14/15 (middle)
#: come from the same six 7-byte stubs at RVA 0x40254-0x40277 and match the
#: documented Win32 right/middle constants exactly, so the mapping is sound —
#: but no such record has ever been seen, and the single-finger iPad input
#: observed so far could not have produced one. Do not claim these work.
EVDEV_BUTTON_FOR_FIELD0 = {
    5: BTN_LEFT,
    6: BTN_LEFT,
    8: BTN_RIGHT,
    9: BTN_RIGHT,
    14: BTN_MIDDLE,
    15: BTN_MIDDLE,
}

#: ``field0`` values that press rather than release. Down/up alternate within
#: each pair, as observed for 5/6.
_FIELD0_PRESSED = {5: True, 6: False, 8: True, 9: False, 14: True, 15: False}


@dataclass(frozen=True)
class InjectionCall:
    """One D-Bus call to make on ``org.gnome.Mutter.RemoteDesktop.Session``.

    Kept as data rather than performed immediately so a plan can be asserted
    against the observed records offline, with no session and no compositor.
    """

    method: str
    args: tuple[object, ...] = field(default_factory=tuple)

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{self.method}{self.args}"


def plan_injection(
    field0: int,
    x: int,
    y: int,
    *,
    stream_path: str,
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
) -> list[InjectionCall]:
    """Translate one inbound input record into RemoteDesktop calls.

    ``x``/``y`` are the record's coordinates, which FED-LIVE-E001 confirmed are
    **monitor-relative pixels** in the display's own 1280x960 space.

    **Fact (FED-DBUS-E001): they pass straight through.** For a virtual stream
    the whole of ``meta_stream_transform_position`` is

        ``*x = stream_x + view_layout.x``  (and the same for y)

    — a pure translation by the monitor's position in the stage, with no scaling
    and no normalisation. So the Windows agent's virtual-desktop transform,
    ``((value + monitor_origin - desktop_origin) / desktop_span) * 65535``, has
    **no Linux equivalent to reproduce**; Mutter adds the offset itself. The
    coordinates go in as doubles, unchanged.

    **Inference — a button event is preceded by a motion call.** The iPad sends
    coordinates with every record, including downs and ups, and a tap arrives as
    a bare ``5 -> 6`` with no motion record before it (FED-LIVE-E001 saw ten).
    Pressing without moving first would land the press wherever the pointer
    happened to be, so the position must be applied first. On Windows this is
    one ``SendInput`` whose flags combine the positioned-move bits with the
    button constant; on Linux the two are separate calls, and motion must come
    first.

    Returns an empty list for a ``field0`` with no pointer meaning — the
    keyboard values (1, 2), the control-message values (16, 17) and the values
    the agent accepts and ignores. Those are decoded but unexercised, and this
    host does not invent behaviour for them.
    """
    if not stream_path:
        raise GnomeError("stream_path is required; it is the 'stream' argument")
    if not 0 <= x <= width or not 0 <= y <= height:
        raise GnomeError(
            f"coordinate ({x}, {y}) is outside the {width}x{height} display; "
            "FED-LIVE-E001 observed every value inside it, so this is a decode "
            "or configuration fault rather than something to clamp"
        )

    motion = InjectionCall(
        "NotifyPointerMotionAbsolute", (stream_path, float(x), float(y))
    )

    if field0 in EVDEV_BUTTON_FOR_FIELD0:
        return [
            motion,
            InjectionCall(
                "NotifyPointerButton",
                (EVDEV_BUTTON_FOR_FIELD0[field0], _FIELD0_PRESSED[field0]),
            ),
        ]

    # field0 10 is motion (FED-LIVE-E001: 1,368 of 1,449 records). 4 and 7 are
    # the statically decoded movement-only values, which take the same mouse
    # path with no button stub; neither has been observed.
    if field0 in (10, 4, 7):
        return [motion]

    return []


# ---------------------------------------------------------------------------
# Live session — nothing below runs until explicitly called
# ---------------------------------------------------------------------------


class VirtualDisplaySession:
    """Creates a Mutter virtual monitor and injects input into it.

    **This has user-visible effects.** Starting a session makes a new monitor
    appear on the desktop and raises a screen-sharing indicator. Construction
    is inert; :meth:`open` is the call that touches the bus.

    **Never executed.** Every signature it uses is verified (FED-DBUS-E001), but
    the composition — the ordering below, and the claim that these calls add up
    to a working extended display — is a design **Inference** that no run has
    confirmed. Treat the first execution as the experiment it is.
    """

    def __init__(
        self,
        *,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        refresh_rate: float = TARGET_REFRESH,
        cursor_mode: int = CURSOR_MODE_EMBEDDED,
        is_platform: bool | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.refresh_rate = refresh_rate
        self.cursor_mode = cursor_mode
        self.is_platform = is_platform

        self._bus = None
        self._remote_desktop_session = None
        self._screen_cast_session = None
        self._started = False
        self.session_id: str | None = None
        self.stream_path: str | None = None
        self.node_id: int | None = None
        #: Whether something is actually consuming the PipeWire stream.
        #:
        #: **Fact, measured 2026-11-08.** Absolute motion is silently dropped
        #: until the stream has a consumer. With Mutter's idle timer as the
        #: probe: 40 motion calls with no consumer left idle climbing
        #: 14,741 -> 15,605 ms, and the same burst with a consumer attached
        #: took it 20,683 -> 21 ms. The D-Bus calls return success either way,
        #: so nothing in the reply distinguishes the two.
        #:
        #: The cause is in ``meta_stream_virtual_transform_position``: it
        #: returns FALSE unless ``meta_stream_source_is_enabled`` and the
        #: source has a ``ClutterStageView``, and the caller then logs
        #: "Dropping early absolute pointer motion" and completes the call.
        #: ``NotifyPointerButton`` takes no stream and no transform, so it
        #: lands regardless — which is why a host in this state produces
        #: clicks at a stale pointer position: selected text and windows
        #: behaving oddly, with a pointer that never moves.
        self.stream_consumed = False

    # -- helpers ----------------------------------------------------------

    def _proxy(self, bus_name: str, object_path: str, interface: str):
        from gi.repository import Gio  # noqa: PLC0415

        if self._bus is None:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return Gio.DBusProxy.new_sync(
            self._bus,
            Gio.DBusProxyFlags.NONE,
            None,
            bus_name,
            object_path,
            interface,
            None,
        )

    @staticmethod
    def _version_of(proxy) -> int:
        value = proxy.get_cached_property("Version")
        if value is None:
            raise GnomeError(
                "no Version property on the interface — this does not look "
                "like the Mutter API FED-DBUS-E001 verified"
            )
        return int(value.unpack())

    # -- lifecycle --------------------------------------------------------

    def open(self, *, require_verified_versions: bool = True) -> int:
        """Create both sessions, pin the monitor and start the stream.

        Returns the PipeWire ``node_id`` to hand to ``pipewiresrc path=``.

        The ordering is the one FED-DBUS-E001 derived: the remote-desktop
        session first, because the screen cast is bound to it by id and "remote
        desktop driven screen casts are started and stopped by the remote
        desktop session"; the stream's ``PipeWireStreamAdded`` subscription
        before ``Start``, so the node id cannot be missed.
        """
        from gi.repository import GLib  # noqa: PLC0415

        remote_desktop = self._proxy(
            REMOTE_DESKTOP_BUS_NAME, REMOTE_DESKTOP_OBJECT_PATH, REMOTE_DESKTOP_IFACE
        )
        screen_cast = self._proxy(
            SCREEN_CAST_BUS_NAME, SCREEN_CAST_OBJECT_PATH, SCREEN_CAST_IFACE
        )

        if require_verified_versions:
            check_versions(
                self._version_of(screen_cast), self._version_of(remote_desktop)
            )

        supported = remote_desktop.get_cached_property("SupportedDeviceTypes")
        if supported is not None and not supports_device_types(
            int(supported.unpack()), DEVICE_TYPE_POINTER
        ):
            raise GnomeError(
                f"RemoteDesktop reports SupportedDeviceTypes="
                f"{int(supported.unpack())}, which lacks pointer support"
            )

        # 1. remote desktop session, and its id
        rd_path = remote_desktop.call_sync(
            "CreateSession", None, 0, -1, None
        ).unpack()[0]
        self._remote_desktop_session = self._proxy(
            REMOTE_DESKTOP_BUS_NAME, rd_path, REMOTE_DESKTOP_SESSION_IFACE
        )
        session_id = self._remote_desktop_session.get_cached_property("SessionId")
        if session_id is None:
            raise GnomeError("the remote desktop session exposed no SessionId")
        self.session_id = str(session_id.unpack())

        # 2. screen cast session bound to it
        # GLib.Variant("(a{sv})", (prebuilt,)) does NOT work: PyGObject's
        # format-string creator tries to iterate the already-built a{sv}
        # variant as a Python dict and raises KeyError. new_tuple wraps it
        # properly.
        sc_path = screen_cast.call_sync(
            "CreateSession",
            GLib.Variant.new_tuple(
                to_glib_variant_dict(
                    screen_cast_session_properties(self.session_id)
                )
            ),
            0,
            -1,
            None,
        ).unpack()[0]
        self._screen_cast_session = self._proxy(
            SCREEN_CAST_BUS_NAME, sc_path, SCREEN_CAST_SESSION_IFACE
        )

        # 3. the pinned virtual monitor
        properties = record_virtual_properties(
            [
                virtual_monitor_mode(
                    self.width, self.height, self.refresh_rate
                )
            ],
            cursor_mode=self.cursor_mode,
            is_platform=self.is_platform,
        )
        self.stream_path = self._screen_cast_session.call_sync(
            "RecordVirtual",
            GLib.Variant.new_tuple(to_glib_variant_dict(properties)),
            0,
            -1,
            None,
        ).unpack()[0]

        # 4. subscribe before starting, so the node id cannot be missed
        stream = self._proxy(
            SCREEN_CAST_BUS_NAME, self.stream_path, SCREEN_CAST_STREAM_IFACE
        )
        loop = GLib.MainLoop()

        def on_signal(_proxy, _sender, signal, params):
            if signal == "PipeWireStreamAdded":
                self.node_id = int(params.unpack()[0])
                loop.quit()

        handler = stream.connect("g-signal", on_signal)

        # 5. starting the remote desktop session starts the cast with it
        try:
            self._remote_desktop_session.call_sync("Start", None, 0, -1, None)
            self._started = True
            if self.node_id is None:
                GLib.timeout_add_seconds(10, loop.quit)
                loop.run()
        finally:
            stream.disconnect(handler)

        if self.node_id is None:
            raise GnomeError(
                "no PipeWireStreamAdded signal arrived within 10s; the stream "
                "never started, so there is no node to capture from"
            )
        return self.node_id

    def stream_parameters(self) -> dict[str, object]:
        """Read the stream's ``Parameters`` dictionary.

        **Do not expect ``size`` or ``position`` here — a virtual stream has
        neither.** Observed 2026-11-08: the only key present is ``mapping-id``.
        ``set_stream_parameters`` in ``meta-screen-cast-stream.c`` has branches
        for monitor, area and window streams and **none for virtual**, and it
        runs once in ``initable_init``, before the virtual monitor exists — so
        it could not report a size even if it tried. ``mapping-id`` appears
        only because a remote-desktop session is attached.

        This corrects the FED-DBUS-E001 write-up, which suggested asserting the
        pinned geometry here. Assert it on the **negotiated PipeWire caps**
        instead: the capture pipeline pins width and height, so a stream of any
        other size fails negotiation rather than producing wrong-sized frames.
        """
        if self.stream_path is None:
            raise GnomeError("no stream; call open() first")
        stream = self._proxy(
            SCREEN_CAST_BUS_NAME, self.stream_path, SCREEN_CAST_STREAM_IFACE
        )
        value = stream.get_cached_property("Parameters")
        return {} if value is None else dict(value.unpack())

    def inject(self, field0: int, x: int, y: int) -> list[InjectionCall]:
        """Apply one inbound input record. Returns the calls actually made.

        **A successful return does not prove delivery.** Mutter's
        ``transform_position`` returns FALSE until the stream has a
        ``ClutterStageView``, and the handler then logs "Dropping early absolute
        pointer motion" and completes the call successfully anyway. So early
        events are silently discarded, and no error surfaces here.
        """
        if self._remote_desktop_session is None or self.stream_path is None:
            raise GnomeError("no session; call open() first")
        if not self.stream_consumed:
            raise GnomeError(
                "refusing to inject: nothing is consuming the PipeWire stream "
                "yet, so Mutter would silently drop every absolute motion "
                "while still reporting success. Buttons would still land, at "
                "a stale pointer position — which looks like selected text "
                "and misbehaving windows rather than an error. Start the "
                "capture and pull at least one frame, then set "
                "stream_consumed."
            )

        from gi.repository import GLib  # noqa: PLC0415

        calls = plan_injection(
            field0, x, y,
            stream_path=self.stream_path,
            width=self.width,
            height=self.height,
        )
        signatures = {
            "NotifyPointerMotionAbsolute": "(sdd)",
            "NotifyPointerButton": "(ib)",
        }
        for call in calls:
            self._remote_desktop_session.call_sync(
                call.method,
                GLib.Variant(signatures[call.method], call.args),
                0,
                -1,
                None,
            )
        return calls

    def close(self) -> list[str]:
        """Stop the session and release the virtual monitor.

        Returns the teardown errors it swallowed, if any.

        **Teardown must never mask the failure that caused it.** Stopping a
        session that was never started raises "Session not started", so an
        early failure in :meth:`open` would otherwise surface as that instead
        of its real cause. Each Stop is attempted and its error recorded, and
        the state is cleared either way so a dangling virtual monitor cannot
        survive a partially opened session.
        """
        errors: list[str] = []
        # Stopping the remote desktop session stops the cast with it and
        # destroys the screen cast session object, so only fall back to
        # stopping the cast directly if the remote desktop stop did not
        # happen or failed. Observed: stopping both in sequence makes the
        # second call fail with "Object does not exist at path ...".
        stopped = False
        if self._remote_desktop_session is not None:
            try:
                self._remote_desktop_session.call_sync("Stop", None, 0, -1, None)
                stopped = True
            except Exception as exc:  # noqa: BLE001 - teardown is best effort
                errors.append(f"{type(exc).__name__}: {exc}")
        if not stopped and self._screen_cast_session is not None:
            try:
                self._screen_cast_session.call_sync("Stop", None, 0, -1, None)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")
        self._remote_desktop_session = None
        self._screen_cast_session = None
        self._started = False
        self.stream_path = None
        self.node_id = None
        return errors

    def __enter__(self) -> VirtualDisplaySession:
        self.open()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
