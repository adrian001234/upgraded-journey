# Tiny Lawn Tales - Show Bible
Written 2026-10-10, updated 2026-10-11 (hero renamed from Nori to Mimsi). Update this file whenever a decision changes.

## The channel
- Name: Tiny Lawn Tales (backup: Under the Mossy Log)
- Tagline: Tiny stories. No words. Big laughs.
- Video titles: "Mimsi and the Giant Crumb | Tiny Lawn Tales"
- Audience: little kids AND their parents. Wordless, so it works in any language.
- Look: photoreal 3D macro-world, sunny lawn, Minuscule-style backgrounds.

## The hero: Mimsi the snail (girl)
Spelled M-I-M-S-I, always, with an "i" at the end (owner confirmed 2026-10-11).
Reference picture (saved in Supabase):
https://dbdtwhzlmzhyidpmeymn.supabase.co/storage/v1/object/public/video_clips/refs/mimsi.png
(The file used to be called pip.png and was renamed to mimsi.png. The repo variable
CHARACTER_REFERENCE_URL must point to refs/mimsi.png.)

Repeat this EXACT description in every shot she appears in. The video model has no
memory between clips. Every shot that features her must contain the exact words
"Mimsi the snail" (the video code looks for that phrase to attach her reference picture;
it must match the repo variable CHARACTER_REFERENCE_NAME exactly):

Mimsi the snail, a small cute garden snail with a friendly happy face. Soft pale
tan-yellow body, two short eyestalks, each with one big round shiny eye with a brown
iris, a small smiling mouth, and a smooth bright orange spiral shell with one
cream-colored swirl line.

Her recognition marker is the bright orange shell with the cream swirl.
Her emotions live in her eyestalks: they pop out, droop, spin, look at each other.

## Recurring things (repeat these EXACT descriptions in every shot they appear in)
Sparrow: a small sparrow with a round fluffy body, streaky brown and cream feathers,
a short pale cone-shaped beak and one big curious round black eye.

Log and door: a mossy fallen log covered in soft green moss, with a tiny round wooden
door painted warm yellow and one small round window beside it.

Sprinkler: a small garden sprinkler with a green plastic body on a short stand, spraying
a sweeping arc of water droplets that catch the sunlight.

Crumb: a huge golden cookie crumb with a rough sandy-brown surface and tiny chocolate
speckles, glittering in the sun, much bigger than the snail.

## World rules
- No humans, no talking, no text on screen.
- The only other creature with a face is the sparrow (our recurring rival: sometimes
  villain, sometimes accidentally helpful). Other bugs only as background if needed.
- Never two close-ups in a row. At least 1 in 4 shots must be wide.
- Gentle danger only. Nobody is really hurt. Bad moments always end in comedy.
- Every episode ends on a warm button gag.

## Story rules (what makes it funny for kids AND adults)
1. A gag or a clear emotion every 5 to 8 seconds. No shot exists just to look pretty.
2. Mimsi wants ONE simple thing. The lawn keeps getting in the way.
3. Rule of three: try, fail, try again with a twist, then a surprise payoff.
4. Two layers of humor: kid layer (falls, boings, squeaks, funny faces) and adult layer
   (relatable struggles, slow-motion chases, movie-style moments, a hero who loses
   everything and still wins).
5. Must make sense with the sound OFF. Eyes and body carry the joke; sound adds to it.
6. Sound is the language: music plus effects (splat, boing, squeak, gasp, sprinkler).
7. Slow snail vs fast world is the comedy engine. A sudden sprint is a classic gag.

## Episode 1: "Mimsi and the Giant Crumb" (about 2m50s, 40 shots, 4 acts)
- Act 1, the find: Mimsi's eyes pop at a cookie crumb bigger than she is. She tries to
  bite it (rock hard), lift it (flattened), then balances it on her shell like a hat.
- Act 2, the struggle: an uphill slope - climb, slip back, climb, slip back, then a
  fake-heroic dash that flops. Then the sprinkler: she times her run to its rhythm like
  a video game.
- Act 3, the lawn fights back: the sparrow spots the crumb. Slow-motion chase (slow
  snail vs fast bird). Mimsi hides in her shell, the sparrow pecks it and bonks itself,
  the shell spins like a top and the sparrow gets dizzy.
- Act 4, the payoff: Mimsi reaches her tiny door and the crumb does not fit. She pushes,
  turns it, gets it stuck. Ending gag: the sparrow takes the crumb after all and Mimsi
  slides home without it, happy and free.
The full 40-shot list is in EPISODE_01_SHOTS.md (draft 1). The owner has not yet approved the story.

## Technical notes
- Each episode is one row in the Supabase table video_pipeline, inserted with status
  'narrated', with shot_list (each shot has visual_description) and shot_durations
  (same length as shot_list), plus an audio track URL in narration_url (the assembly
  stage needs it - for this show it is the music and sound-effect track, not narration).
- Watch for: using the same reference picture as the start of every shot may make clips
  begin in the same pose. If so, use it only for close and medium shots.
