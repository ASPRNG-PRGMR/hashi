# Packaging

The goal is an official **Fedora** package, so that someone with a legacy iPad —
a device with no remaining use and no path to a current iPadOS — can install
HASHI with `dnf` and get a second screen out of hardware that would otherwise be
a drawer ornament. That is the use case worth packaging for, and it is why
Fedora is the first target rather than a Flatpak or a curl-pipe-sh installer.

Status: **nothing is packaged yet.** This document is the plan and the list of
things that must be true first.

## Why Fedora first

- The project is developed on Fedora against GNOME/Mutter, which is Fedora's
  default session. The supported configuration and the distribution's default
  configuration are the same thing.
- Every runtime dependency — `usbmuxd`, PipeWire, GStreamer, PyGObject, Pillow,
  libjpeg-turbo — is already a Fedora package. Nothing has to be bundled.
- Fedora's review process is strict about licensing and bundling, which is
  exactly the scrutiny an interoperability project should want applied to it in
  public.

## Prerequisites before a review request

These are the real blockers. None is hard; none is done.

### 1. Versioned releases

Fedora packages build from a stable release tarball, not from a moving branch.

- [ ] Adopt a version scheme and tag `v0.1.0`
- [ ] Publish a GitHub release so `%{url}/archive/v%{version}/...` is stable
- [ ] Keep a `CHANGELOG.md` the spec's `%changelog` can track

### 2. An installable layout

Right now everything runs from the checkout via `hashi.sh`. A package needs
real install targets.

- [ ] `pyproject.toml` for the Python host, so Fedora's
      `%pyproject_wheel` / `%pyproject_install` macros apply. The modules
      currently import each other by bare name and the test suite runs with
      `-t .`; that has to become a proper package (`hashi/...`) with a console
      entry point, without breaking the import root the suites rely on
- [ ] `install()` rules in `native/CMakeLists.txt` for the `hashi` binary
- [ ] A single installed launcher that replaces `./hashi.sh` for users, with
      `hashi.sh` kept as the developer entry point
- [ ] Decide what ships: the Python host alone is the honest answer today,
      since it is the only implementation that has run end to end. The C++
      binary should not be packaged before it has been run live.

### 3. Documentation a package must carry

- [ ] A man page (`hashi.1`) — Fedora expects one for a user-facing command
- [ ] `%license LICENSE-MIT LICENSE-APACHE` in the spec; both files ship
- [ ] `%doc README.md`

### 4. Licensing metadata

- [x] Dual MIT OR Apache-2.0, both Fedora-approved licences
- [x] Valid SPDX expression: `License: MIT OR Apache-2.0`
- [ ] SPDX identifier headers on source files
- [ ] Confirm the current Fedora licensing guidelines still accept this
      expression verbatim at submission time — the SPDX migration has moved
      more than once, so check rather than assume

### 5. Quality gates

- [ ] `%check` runs the Python suite and, if the native core is packaged,
      `ctest`. The suites touch no device and need no compositor, so they run
      in Koji unchanged — this is already true and is the main reason the
      offline/live split in the test suite was worth keeping
- [ ] `rpmlint` clean
- [ ] Builds on all Fedora release targets currently supported

### 6. Process

- [ ] Create a FAS account and join the packagers group
- [ ] Find a sponsor (required for a first package)
- [ ] File a Package Review ticket in Red Hat Bugzilla under the
      *Package Review* component
- [ ] Follow the review to completion, then request the dist-git repository and
      build

## Dependencies the spec will declare

Runtime:

```
Requires: usbmuxd
Requires: python3-gobject
Requires: python3-pillow
Requires: gstreamer1-plugins-base
Requires: gstreamer1-plugin-pipewire
Requires: pipewire
```

Build, if the native core is packaged:

```
BuildRequires: cmake gcc-c++ pkgconfig
BuildRequires: turbojpeg-devel glib2-devel
BuildRequires: gstreamer1-devel gstreamer1-plugins-base-devel
```

GNOME/Mutter is a hard runtime requirement but is deliberately **not** a
`Requires:` — the package should install on any Fedora and fail with a clear
message, rather than drag a desktop onto a server.

## Things reviewers will reasonably ask about

Worth having answers ready, because they are fair questions:

- **"Does this redistribute vendor material?"** No. No Splashtop code, binary,
  asset or data table is present. The JPEG parameters are rebuilt from
  published ISO/IEC 10918-1 Annex K tables. See the Legal and scope section of
  the README.
- **"Does it bundle anything?"** No. The Rust core has no crate dependencies
  and the C++ core has no vendored third-party source; both implement the small
  plist subset they need rather than vendoring a library. If the Rust core is
  ever packaged, Fedora's Rust guidelines apply — with zero dependencies that
  is close to trivial.
- **"Does it need root or a kernel module?"** No. Everything is userspace,
  through Mutter's existing permission-mediated D-Bus APIs.
- **"Is it maintained?"** Answer honestly, including the alpha status and the
  single-maintainer reality.

## Other targets

Secondary, and only after Fedora:

- **Flatpak** — awkward. The host needs the `usbmuxd` Unix socket and Mutter's
  `ScreenCast`/`RemoteDesktop` D-Bus APIs, which means broad portal and socket
  access. Possible, but the sandbox would be wide enough to be worth
  questioning.
- **COPR** — the sensible interim step, and a reasonable place to publish
  builds while the prerequisites above are being worked through.
- **AUR, Debian, openSUSE** — welcome as contributions. The project has no
  access to those distributions to test on.
