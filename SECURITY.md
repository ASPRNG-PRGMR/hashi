# Security policy

## Scope

HASHI is a host-side implementation of a wired display protocol. The parts
worth scrutinising are:

- **Inbound record parsing** (`hashi_stream`, `native/src/stream.cpp`,
  `rust/src/stream.rs`) — this parses data that arrives from the tablet over
  USB. It is the only attacker-controlled input path in the project.
- **The usbmux/plist layer** — a hand-written subset of Apple's plist format,
  parsing responses from the local `usbmuxd` socket.
- **Input injection** — HASHI injects pointer events into the compositor on
  behalf of the connected device.

A device on the other end of the cable can move your pointer and click. That is
the feature. It is still worth stating plainly: **plugging in a tablet running
HASHI grants that tablet control of your pointer.**

HASHI needs no root and loads no kernel module. It runs entirely as your user,
and the virtual monitor and input injection both go through Mutter's existing
permission-mediated D-Bus APIs.

## Reporting a vulnerability

Please report privately rather than in a public issue.

Use GitHub's [private vulnerability
reporting](https://github.com/ASPRNG-PRGMR/hashi/security/advisories/new) on
this repository. If that is unavailable to you, open a public issue saying only
that you have a security report and asking for a contact — no details.

Please include:

- what you did, and what happened
- the affected component and, if you have it, a minimal reproducer
- versions: HASHI commit, GNOME/Mutter, distribution, iPad and app version

Expect an acknowledgement within a week. This is a small project maintained by
one person; it has no SLA, and saying so is more useful than promising one.

## Disclosure

Fixes land in public commits with the issue described. If you want credit, say
so and name how you would like to be credited.

## Out of scope

- Vulnerabilities in Splashtop's own software. Report those to Splashtop.
- Vulnerabilities in Mutter, PipeWire, GStreamer, libjpeg-turbo or usbmuxd.
  Report those upstream; mention here if HASHI's usage makes one reachable.
- The fact that a connected device can control the pointer, which is the
  documented purpose of the tool.
