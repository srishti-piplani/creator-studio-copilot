# Direct versus software monitoring and latency

## Two listening paths, one recording
Direct monitoring sends the interface's input toward headphones or speakers without making the full trip through the DAW. Software monitoring returns the input through the computer, where track effects and routing can influence what you hear. The recorded file and the performer's monitoring path are related but distinct: choosing hardware monitoring does not inherently stop the DAW from recording that input.

Software monitoring introduces processing and buffering delay. Smaller audio buffers often reduce the buffering contribution but demand more timely processing. Converter, driver and plug-in delays can remain. Direct monitoring is commonly described as near-zero latency; this should not be interpreted as every physical stage taking literally zero time. Its main advantage is avoiding the computer's round trip for the monitored input.

## Choose the path for the performance
A singer who mainly needs pitch and timing feedback may prefer the direct input alongside DAW backing tracks. A guitarist who needs a software amplifier must hear the processed path to judge that sound. Hardware mixers differ, and this guide does not assume a particular Solo or 2i2 switch layout. Decide which signal the performer needs, then configure the appropriate route.

1. Record a short dry phrase and confirm that input routing works.
2. Listen with only the direct path enabled.
3. Listen with only the software return enabled.
4. Compare responsiveness and the effects you actually need.
5. Keep a deliberate single path unless a blended arrangement is intentional.

## Worked troubleshooting example
A singer reports an echo only while recording. The direct input is audible immediately, and software monitoring returns another copy later. Changing EQ will not align those two paths. Disable one input-monitoring route, then listen again while preserving the backing track. Do not mute an unrelated playback bus merely because it is convenient.

## Misconceptions and limits
Direct monitoring normally bypasses DAW insert effects; it cannot be assumed to include a software reverb or amplifier. Reducing the buffer is not guaranteed to cure every delay, especially with lookahead or heavy processing. Conversely, delayed monitoring is not proof that a correctly timed file has been written late. Inspect the actual recording separately. This guide explains route choices, not an exact driver configuration or a promised latency value for a named interface.
