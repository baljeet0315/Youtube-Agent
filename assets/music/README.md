# Background music

Drop royalty-free tracks here, one folder per mood:

```
assets/music/
  calm/        *.mp3
  mysterious/  *.mp3
  tense/       *.mp3
  uplifting/   *.mp3
  energetic/   *.mp3
```

The renderer picks a random track for the script's `music_mood`, loops or trims
it to the video length, mixes it at `MUSIC_VOLUME` (default 12%) under the voice,
and fades it out over the closing tail.

Alternative: upload the same folder structure to the R2 bucket under `music/<mood>/`
— no redeploy needed, the worker lists R2 at render time.

Use tracks you are licensed to use on YouTube (e.g. Pixabay Music, Uppbeat,
YouTube Audio Library). Keep files small (128 kbps mp3 is plenty).
