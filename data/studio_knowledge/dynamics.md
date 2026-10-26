# Compression, limiting and de-essing

## Dynamics processing changes level behavior
A downward compressor reduces gain when its detector responds above a threshold. Ratio describes the steady-state relationship above that threshold. In an ideal hard-knee example, a 4:1 ratio turns an input excursion of 8 dB above threshold into about 2 dB above threshold at the output, before makeup gain. That arithmetic is a teaching example, not a prediction of every real compressor's transient response.

Attack and release shape how gain reduction builds and recovers. Their behavior depends on the processor and material, so a fast setting is not simply better. Makeup gain changes output level; it does not reverse the internal dynamic changes. Compare processed and bypassed audio at similar loudness before deciding whether compression actually helps.

## Three tools with different jobs
A compressor can control performance variation or shape articulation. A limiter emphasizes constraining peaks; its exact behavior and whether it accounts for reconstructed true peaks depend on the implementation. A de-esser reduces excessive sibilance, often by responding to a selected high-frequency region. A static EQ cut affects that region continuously, whereas de-essing can act chiefly during the offending consonants. None of these tools can reliably reconstruct an overloaded analog recording.

## A practical vocal experiment
1. Use clip-level editing for an isolated word that is much louder than the rest.
2. Try gentle compression if the remaining performance still varies excessively.
3. Check whether consonants become more prominent after the level change.
4. Use a de-esser only if sibilance is actually distracting.
5. Recheck the voice in context and at matched listening level.

## Original comparison
Suppose a speaker's tone is balanced but their distance from the microphone changes. Compression may reduce level swings, while a broad EQ boost changes the sound of both loud and quiet words. If only certain consonants are piercing, a targeted de-esser might preserve more overall brightness than cutting all high frequencies. The diagnosis determines the tool, not the order in a generic preset chain.

## Misconceptions and limits
A high ratio alone does not define a good limiter. Compression does not always make sound louder until output level is adjusted. Excessive de-essing can damage intelligibility, and aggressive limiting can alter transients. This guide intentionally supplies no mandatory threshold, attack time, loudness target or product-specific dynamics settings.
