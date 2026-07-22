# TechPulse — AI Video Pipeline

Niche: Tech / AI / Science news briefs (short, punchy, "here's what just changed" style)

## Pipeline Stages

1. **Research** — daily trending tech/AI/science topic sourcing (free news APIs / RSS)
2. **Script** — FreeLLMAPI generates the news-brief script from sourced topics
3. **Voice/Video** — Agnes AI + free-credit gateway stack generates video assets
4. **Tracking** — Supabase table logs status per video: sourced → scripted → generated → ready
5. **Publish** — pushes finished video to the TechPulse channel (stub until channel is live)
6. **Analytics** — post-publish performance tracking (added after first videos are live)

## Status
- Channel: TechPulse — pending YouTube ID verification (~24hr)
- Current stage: building Research module (step 2)
