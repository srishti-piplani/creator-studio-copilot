# MIDI, quantization and velocity

## Instructions are different from a recorded waveform
MIDI note data tells an instrument what and when to play. It is not itself a recording of a vibrating string or a microphone's electrical output. A MIDI clip can contain note positions, durations and velocity values; the receiving instrument turns those instructions into sound. This distinction explains why a MIDI activity light can move while the output remains silent: note messages may arrive without a valid instrument or audio route.

Quantization adjusts event timing toward chosen rhythmic positions. The grid represents an interpretation of musical time, not a measurement of whether a performance is artistically correct. A partial timing correction can preserve some of a player's feel; a completely rigid grid can be useful for other material. Velocity is a performance value, not a guaranteed output-volume setting. Depending on the instrument, it can influence loudness, timbre or several responses together.

## Original timing example
Imagine four intended beats in a phrase, with the last note placed deliberately late for emphasis. First duplicate the clip. On one copy, quantize all four notes tightly. On the other, correct only the obvious accidental early note. Listen against the same accompaniment. The difference lets you decide whether the musical effect came from timing rather than from a different sound preset. This is an experiment, not a rule that edited performances must retain every mistake.

## Diagnose a silent keyboard
1. Verify that MIDI messages reach the intended track.
2. Check that the track addresses a software instrument or the right external destination.
3. Confirm a playable note range and audible instrument patch.
4. Inspect the instrument's audio output and the monitoring route.
5. Record a few notes and inspect the clip independently of the live performance.

Do not turn on microphone phantom power to solve a MIDI routing problem. Similarly, changing audio input gain is not the same as editing note velocity.

## Misconceptions and limits
Quantization is not pitch correction. A velocity change need not behave like a track-fader change, and MIDI notes do not guarantee that an external synthesizer's audio has been recorded. This guide does not specify a product's exact MIDI-channel menu or controller protocol. Its purpose is to separate note instructions, sound generation and audio monitoring so troubleshooting can target the correct stage.
