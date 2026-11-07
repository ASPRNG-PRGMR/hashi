"""Capture output-dimension rules established in FED-MODE-E001.

Two very different confidence levels live in this module, and callers must not
mix them up:

* :func:`monitor_extent` and :func:`select_monitor_dimensions` are **Fact**.
  They reproduce instruction-level behaviour of the unchanged agent
  (SHA-256 cb9ab63be48947344e6d0e5e718e5522e707c64473dac6cc026149424964e52c)
  and are corroborated numerically by the observed runtime values in
  WIN-BACKEND-E003/E004.

* :func:`best_resolution_score` and :func:`select_best_resolution` are an
  **Inference**: a reconstruction of ``CMultiDisplay::FindBestResolution``
  (RVA 0x42530) read out of instructions and never executed on Windows. They
  exist to analyse and predict, and are deliberately not wired into anything.
  Do not treat their output as an observed value, and do not use them to drive a
  host implementation.

Nothing here implements a handshake, a resize negotiation, a codec or any
control message. See docs/fedora-mode-selection.md for addresses and evidence.
"""

from dataclasses import dataclass
from fractions import Fraction

# Static preferred base of the inspected agent image.
PREFERRED_BASE = 0x400000

# Upper bound CCaptor::CustomizeResolution enforces on ForceResW * ForceResH
# (cmp eax, 0x7e9000 at RVA 0x32699). 3840 * 2160 pixels.
CUSTOMIZE_RESOLUTION_PIXEL_LIMIT = 0x7E9000


class ModeError(ValueError):
    pass


@dataclass(frozen=True)
class MonitorRecord:
    """One 32-byte monitor record as built at RVA 0x3ca00.

    ``width`` and ``height`` mirror record fields +0x10 and +0x14, which the
    agent derives from ``MONITORINFOEXW.rcMonitor`` rather than from any mode
    request. ``device`` mirrors the name copied from ``szDevice`` (+0x28).
    """

    left: int
    top: int
    right: int
    bottom: int
    device: str = ""

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def monitor_extent(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    """Return ``(width, height)`` for an ``rcMonitor`` ``(left, top, right, bottom)``.

    **Fact.** Record append at RVA 0x3ca00 computes ``right - left`` into record
    +0x10 and ``bottom - top`` into record +0x14. The width getter 0x3cde0 and
    height getter 0x3ce50 return those two fields, and both monitor-refresh
    paths store them into shared state +0x1c/+0x20, which ordinary JPEG
    initialization at RVA 0x3b750 then receives.
    """
    if len(rect) != 4:
        raise ModeError("rcMonitor needs exactly four values")
    left, top, right, bottom = rect
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise ModeError(f"non-positive monitor extent {width}x{height}")
    return width, height


def select_monitor_dimensions(
    records: list[MonitorRecord], index: int
) -> tuple[int, int]:
    """Return the dimensions the getters would yield for ``index``.

    **Fact.** Both getters read the selected index from monitor-info +0x00 and,
    when it is not below the record count, replace it with ``count - 1`` before
    indexing (``cmp``/``jb`` then ``dec`` at 0x3cdfa-0x3ce11 and
    0x3ce6a-0x3ce81). A negative index is not reachable through that unsigned
    comparison and is rejected here rather than silently wrapped.
    """
    if not records:
        raise ModeError("no monitor records")
    if index < 0:
        raise ModeError(f"negative monitor index {index}")
    if index >= len(records):
        index = len(records) - 1
    record = records[index]
    return record.width, record.height


def best_resolution_score(
    requested: tuple[int, int], candidate: tuple[int, int]
) -> int:
    """Reconstructed ``FindBestResolution`` score; lower is better.

    **Inference, not Fact.** Reconstructed from RVA 0x427a3-0x42869:

    * an aspect penalty ``(100 * |ch*reqW - cw*reqH|) / reqH / ch`` using two
      truncating integer divisions, in that order;
    * ``5 * |reqW - cw|``, tripled when the candidate width is not smaller than
      the requested width;
    * ``|reqH - ch|``, tripled when the candidate height is not smaller than the
      requested height;
    * the whole score divided by 10 when the aspect ratios compare exactly equal.

    The x87 comparison at 0x427ee is modelled with exact rationals. That is
    faithful for the integer dimensions involved here, but it is a model: the
    formula has never been checked against the agent's own per-candidate log.
    """
    req_w, req_h = requested
    cand_w, cand_h = candidate
    if min(req_w, req_h, cand_w, cand_h) <= 0:
        raise ModeError("resolutions must be positive")

    aspect_equal = Fraction(req_w, req_h) == Fraction(cand_w, cand_h)

    cross = abs(cand_h * req_w - cand_w * req_h)
    score = (cross * 100) // req_h // cand_h
    score += 5 * abs(req_w - cand_w) * (3 if cand_w >= req_w else 1)
    score += abs(req_h - cand_h) * (3 if cand_h >= req_h else 1)
    if aspect_equal:
        score //= 10
    return score


def select_best_resolution(
    requested: tuple[int, int], modes: list[tuple[int, int]]
) -> tuple[int, int]:
    """Reconstructed mode choice: the lowest-scoring enumerated mode.

    **Inference, not Fact.** Modes with an odd width or height are discarded,
    matching the two ``test ... 0x1`` guards at RVA 0x42604/0x4260e. Ties keep
    the earliest mode in enumeration order.
    """
    usable = [m for m in modes if m[0] % 2 == 0 and m[1] % 2 == 0]
    if not usable:
        raise ModeError("no even-dimension modes to choose from")
    return min(usable, key=lambda m: best_resolution_score(requested, m))


def customize_resolution_would_apply(
    mirror_mode: int, force_res_w: int, force_res_h: int
) -> bool:
    """Whether ``CCaptor::CustomizeResolution`` would reach its mode change.

    **Fact.** The gate order at RVA 0x3264b-0x32699 is: shared state non-null,
    then ``shared[+0x44] != 0`` (MirrorMode), then the ``ForceResW``/``ForceResH``
    product nonzero and not above
    :data:`CUSTOMIZE_RESOLUTION_PIXEL_LIMIT`. Only then does it call
    ``ChangeDisplaySettingsExW`` at RVA 0x3275a.

    Because the LCI rung of the InitCaptor ladder requires ``+0x44 == 0``
    (FED-BACKEND-E001), this returns False for every LCI configuration.
    """
    if mirror_mode == 0:
        return False
    pixels = force_res_w * force_res_h
    return 0 < pixels <= CUSTOMIZE_RESOLUTION_PIXEL_LIMIT
