# Audio interfaces, gain staging and clipping

## Follow the signal before moving controls
An audio interface connects compatible analog inputs and outputs with computer audio. A microphone preamp raises a small microphone signal before conversion. Input gain, track level, bus level and headphone volume are different points in that path. Raising a headphone control can improve listening comfort without changing the stored recording; raising an input control can change what reaches the converter. A line-level source and a microphone also require different input assumptions.

Digital full scale, expressed as 0 dBFS on conventional peak meters, is a reference ceiling, not a recommended recording target. Headroom is the space between expected peaks and overload. Several individually acceptable tracks can overload a later sum. A low output fader does not prove that an earlier input or effect has stopped clipping. Floating-point processing inside a DAW does not make an overloaded analog preamp or converter recover information it never captured.

## Gain staging as an experiment
1. Trace microphone or instrument, interface input, track, effects, buses and outputs.
2. Perform the loudest likely passage while watching the input meter.
3. Leave room for surprises rather than trying to fill every meter.
4. Check each later stage when effects or extra tracks are added.
5. Compare a dry recording with the processed playback at similar loudness.

There is no universal knob position. Different sources, distances and microphones produce different electrical levels. A healthy recording does not require the gain knob to match someone else's photograph.

## Worked diagnosis
Suppose a vocal sounds harsh although the master meter is low. Disable the insert effects and inspect the dry recording. If the damage remains, examine the original input path and try another controlled recording at lower gain. If the dry file is clear but playback distorts after a processor, investigate that stage's input and output. This changes one variable at a time rather than hiding the symptom under a quieter master.

## Practical misconceptions
More bits do not excuse clipping, and a limiter after recording cannot reconstruct clipped waveform detail. A compressor is not a substitute for adequate input headroom. Loudness-matched comparisons help prevent the louder version from winning simply because it is louder. Exact meter targets and input sensitivities depend on the recording format and device; this guide does not prescribe a universal safe peak number.
