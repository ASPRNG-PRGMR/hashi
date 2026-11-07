# JPEG frame format — FED-JPEG-E001

Offline work on Fedora, 2026-11-08. Derived from the captured WIN-START-E002
image stream and published standards. Nothing was executed on Windows and
nothing was sent to the iPad.

## Result

**Fact:** all **1,903** captured image records share an identical **623-byte
prelude** — a 609-byte header followed by a 14-byte SOS. Only the entropy-coded
scan data and the trailing `ff d9` differ between frames. The header portion's
SHA-256 is
`3aa000d1d348c7176c24fc4c1cbb12b2172bb5e95689cfeb68008d38dc5f65ad`, and the
segment layout is fixed:

| Segment | Offset | Length |
| --- | --- | --- |
| SOI | 0 | 2 |
| APP0 (JFIF) | 2 | 16 |
| DQT, table 0 | 20 | 67 |
| DQT, table 1 | 89 | 67 |
| SOF0 | 158 | 17 |
| DHT, DC luma (`0x00`) | 177 | 31 |
| DHT, AC luma (`0x10`) | 210 | 181 |
| DHT, DC chroma (`0x01`) | 393 | 31 |
| DHT, AC chroma (`0x11`) | 426 | 181 |
| SOS | 609 | 12 |

## Every byte derives from published standards

This was worth checking carefully, because transcribing vendor data tables into
this repository would cross a clean-room line. It turns out none is needed.

**Fact:** the four Huffman tables are **exactly** the ISO/IEC 10918-1 Annex K
tables — K.3 DC luminance, K.4 DC chrominance, K.5 AC luminance, K.6 AC
chrominance. Their bit counts and value lists match the published values
element for element.

**Fact:** the two quantization tables are **exactly** the Annex K base tables
scaled by the standard IJG quality formula at **quality 80**. This is an exact
match on all 64 coefficients of both tables — total absolute difference zero, not
an approximation. Quality 79 and 81 both fail to reproduce the header hash, and
a test asserts that so the constant cannot be quietly changed.

**Fact:** SOF0 declares 8-bit precision, three components at 1280×960 with
sampling factors `0x22, 0x11, 0x11` — 4:2:0 — and quantization selectors 0, 1, 1.
APP0 is JFIF 1.01 with units = 1 and density 120×120.

So the prelude is fully determined by published tables plus three parameters:
**1280×960, quality 80, density 120.** `hashi_jpeg.build_prelude()` constructs it
from those, and its output reproduces the captured 623 bytes byte-for-byte. This
was verified against **all 1,903 records and all 12 controlled decoded samples**:
1903/1903 and 12/12.

**Inference:** quality 80 is very likely the `quality(%d)` value in the agent's
`captor(%d), fps(%d), quality(%d)` log, which FED-STREAM-E001 found but could not
read. Suggestive and consistent, but the log value itself was never captured, so
this is not Fact.

## Interoperability note, and it matters

Matching these tables is **not required** to talk to the device. JPEG is
self-describing: every frame carries its own DQT and DHT segments, so a host may
emit whatever tables its encoder prefers and the iPad will decode them. Choosing
to reproduce the observed ones is simply the lowest-risk option, and it makes
offline validation exact. A host that needed a different quality or a different
encoder would still interoperate.

## What a host emits

```text
tag-6 record header            (hashi_stream.encode_image_record)
  623-byte prelude             (hashi_jpeg.build_prelude)
  entropy-coded scan data      <-- NOT YET IMPLEMENTED
  ff d9                        (EOI)
```

**Fact:** every captured record ends with `ff d9`.

## Remaining

**The entropy coder is the one missing piece of outbound frame generation.** It
needs the forward DCT, quantization against the tables above, and Huffman coding
with the Annex K tables — in 4:2:0, so chroma is subsampled 2×2. That is ordinary
baseline JPEG work with no protocol unknowns left in it, and it is testable
offline by decoding the result and comparing pixels, exactly as WIN-START-E004
did for the captured samples.

An alternative worth weighing at implementation time: a standard library
(`libjpeg-turbo` via Pillow, or PipeWire-side encoding) at quality 80 with
standard tables would produce a conformant and probably byte-compatible prelude,
at the cost of less control over the exact bytes. Given the interoperability note
above, that is a legitimate choice rather than a compromise.
