## What this changes

<!-- One paragraph. What behaviour differs after this PR? -->

## Why it is correct

<!--
For anything touching the protocol, the encoders or the D-Bus arguments:
what evidence supports this? Label claims Fact / Inference / Hypothesis.
Guessed protocol behaviour is not merged, however plausible.
-->

## Checklist

- [ ] `./hashi.sh` passes (builds, three test suites, conformance)
- [ ] New behaviour has tests
- [ ] If bytes on the wire changed, **all three implementations** were updated
      and conformance still reports 0 mismatches
- [ ] Documentation under `docs/` updated, with claims labelled
      Fact / Inference / Hypothesis
- [ ] No raw captures, pairing records, vendor binaries or frame dumps included
