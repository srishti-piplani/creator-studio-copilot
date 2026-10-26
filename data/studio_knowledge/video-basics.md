# Frame rate, resolution and codecs

## Separate time, detail and storage
Resolution describes the pixel dimensions of an image. Frame rate describes how often frames are presented over time. A codec determines how media is encoded and decoded, while a container packages streams and related information. These are different decisions: an MP4 filename alone does not fully identify the video codec, picture dimensions, audio encoding or playback requirements.

Increasing frame rate and increasing resolution are not interchangeable. More frames describe motion more frequently; more pixels can describe more spatial detail. Neither creates information that was absent from the capture. Motion blur, focus and lighting also affect the visible result. A progressive-frame label should not be confused with a promise about bitrate or compression quality.

## Original arithmetic example
A 1920 by 1080 frame contains 2,073,600 pixel positions. A 3840 by 2160 frame contains four times as many. That does not imply the compressed file must be exactly four times larger, because the encoder and settings still matter. Likewise, a timeline running at 25 frames per second contains 250 frame intervals in ten seconds; changing an interpretation of timing is a different operation from simply choosing a larger frame size.

## Codec decisions in practice
Lossy encoding can discard information to reduce the required data rate. Difficult motion, texture and noise may reveal artifacts when the chosen settings do not preserve enough detail. A delivery codec optimized for convenient playback and an editing-friendly intermediate can solve different workflow needs. Use the intended playback environment to choose compatibility rather than assuming that the smallest file is universally best.

1. Inspect source frame rate, dimensions and codec separately.
2. Choose a project timebase intentionally before extensive editing.
3. Decide whether the goal is editing, archiving or delivery.
4. Test a representative scene on the destination device or service.
5. Keep the original source even if a proxy or converted version is easier to edit.

## Misconceptions and limits
Renaming a file extension does not transcode media. Upscaling cannot guarantee newly captured detail. Frame rate is not shutter speed, and a high-resolution file can still have severe compression artifacts. Exact codecs and frame rates accepted by a platform change, so verify current delivery requirements instead of treating this conceptual guide as a permanent preset list.
