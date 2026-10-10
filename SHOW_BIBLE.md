# Tiny Lawn Tales - Show Bible
Written 2026-10-10. Update this file whenever a decision changes.

## The channel
- Name: Tiny Lawn Tales (backup: Under the Mossy Log)
- Tagline: Tiny stories. No words. Big laughs.
- Video titles: "Nori and the Giant Crumb | Tiny Lawn Tales"
- Audience: little kids AND their parents. Wordless, so it works in any language.
- Look: photoreal 3D macro-world, sunny lawn, Minuscule-style backgrounds.

## The hero: Nori the snail (girl)
Reference picture (saved in Supabase):
https://dbdtwhzlmzhyidpmeymn.supabase.co/storage/v1/object/public/video_clips/refs/pip.png
(The file is called pip.png only because that was her first name. Do not rename it.)

Repeat this EXACT description in every shot she appears in. The video model has no
memory between clips. Every shot that features her must contain the exact words
"Nori the snail" (the video code looks for that phrase to attach her reference picture):

Nori the snail, a small cute garden snail with a friendly happy face. Soft pale
tan-yellow body, two short eyestalks, each with one big round shiny eye with a brown
iris, a small smiling mouth, and a smooth bright orange spiral shell with one
cream-colored swirl line.

Her recognition marker is the bright orange shell with the cream swirl.
Her emotions live in her eyestalks: they pop out, droop, spin, look at each other.

## World rules
- No humans, no talking, no text on screen.
- The only other creature with a face is the sparrow (our recurring rival: sometimes
  villain, sometimes accidentally helpful). Other bugs only as background if needed.
- Never two close-ups in a row. At least 1 in 4 shots must be wide.
- Gentle danger only. Nobody is really hurt. Bad moments always end in comedy.
- Every episode ends on a warm button gag.

## Story rules (what makes it funny for kids AND adults)
1. A gag or a clear emotion every 5 to 8 seconds. No shot exists just to look pretty.
2. Nori wants ONE simple thing. The lawn keeps getting in the way.
3. Rule of three: try, fail, try again with a twist, then a surprise payoff.
4. Two layers of humor: kid layer (falls, boings, squeaks, funny faces) and adult layer
   (relatable struggles, slow-motion chases, movie-style moments, a hero who loses
   everything and still wins).
5. Must make sense with the sound OFF. Eyes and body carry the joke; sound adds to it.
6. Sound is the language: music plus effects (splat, boing, squeak, gasp, sprinkler).
7. Slow snail vs fast world is the comedy engine. A sudden sprint is a classic gag.

## Episode 1: "Nori and the Giant Crumb" (about 2m50s, 40 shots, 4 acts)
- Act 1, the find: Nori's eyes pop at a cookie crumb bigger than she is. She tries to
  bite it (rock hard), lift it (flattened), then balances it on her shell like a hat.
- Act 2, the struggle: an uphill slope - climb, slip back, climb, slip back, then a
  fake-heroic dash that flops. Then the sprinkler: she times her run to its rhythm like
  a video game.
- Act 3, the lawn fights back: the sparrow spots the crumb. Slow-motion chase (slow
  snail vs fast bird). Nori hides in her shell, the sparrow pecks it and bonks itself,
  the shell spins like a top and the sparrow gets dizzy.
- Act 4, the payoff: Nori reaches her tiny door and the crumb does not fit. She pushes,
  turns it, gets it stuck. Ending gag: the sparrow takes the crumb after all and Nori
  slides home without it, happy and free.
The full 40-shot list with one gag marked per shot is still to be written.

## Technical notes
- Each episode is one row in the Supabase table video_pipeline, inserted with status
  'narrated', with shot_list (each shot has visual_description) and shot_durations
  (same length as shot_list), plus an audio track URL in narration_url (the assembly
  stage needs it - for this show it is the music and sound-effect track, not narration).
- Watch for: using the same reference picture as the start of every shot may make clips
  begin in the same pose. If so, use it only for close and medium shots.
