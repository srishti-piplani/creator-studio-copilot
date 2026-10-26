# Audio/video synchronization and drift

## Offset and drift are different observations
An offset means two events are separated by roughly the same amount throughout a recording. Drift means that their relative timing changes as the recording progresses. Moving a clip can correct a constant offset but cannot, by itself, correct a time relationship whose error keeps growing. Start by comparing the beginning and end instead of repeatedly aligning only the opening clap.

A visible clap and its sound, matching waveforms, or compatible timecode can provide alignment evidence. Timecode identifies positions in time; it should not be assumed to force every independent device's sampling clock to remain identical. Digital audio devices that exchange a clocked digital signal need a coherent clock arrangement. Independent recorders can still require duration verification after an initial alignment.

## Original diagnostic example
Imagine a ten-minute interview that is aligned at the opening clap but has a noticeable offset at the closing clap. First check the actual clip durations and the interpretation of their rates. If one track is consistently longer, investigate why before applying an arbitrary repeated nudge. A rate-interpretation error or independent clock difference is a different problem from a fixed processing delay. The observed pattern is evidence, not proof of one particular device fault.

A simple mathematical illustration: if a relative timing difference accumulates at 0.01 seconds per minute, ten minutes adds 0.1 seconds. That hypothetical rate is not a specification for any supported camera or interface. It only explains why a tiny ongoing mismatch becomes visible in a longer take.

1. Compare a shared transient near the beginning.
2. Compare another shared event near the end.
3. Check source durations, intended sample/frame rates and any interpretation settings.
4. Preserve originals before trying a suitable duration or rate correction.
5. Recheck intermediate events and the exported file.

## Common misconceptions
A shared nominal sample rate is not proof that independent clocks are perfectly identical. Waveform alignment does not guarantee continued synchronization, and timecode does not restore a dropped performance. This guide cannot identify a unique cause from one screenshot. Record the pattern, ask about capture settings, and distinguish a plausible explanation from a verified diagnosis. Product-specific resampling, clock wiring and repair procedures need additional documentation.
