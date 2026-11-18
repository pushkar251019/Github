# Recon map: CreatorKit AI Clone (web)

Scope: the AI Clone core loop — one photo + voice -> script -> talking-head video (MP4). AI Actors library and ad-script generator included as "should". Product photos, Shopify app, done-for-you services excluded.
For: the owner's own brands (PS Unfiltered, Unseen Depth of Life) first; a sellable creator/SMB tool second.
Date: 2026-11-18
Method: public pages only (no account, no app code, no private APIs).

## Sources

| # | source | URL | notes |
| --- | --- | --- | --- |
| 1 | AI Clone product page | https://creatorkit.com/ai-clone | inputs, flow, formats, security, $99/10 videos |
| 2 | Pricing | https://creatorkit.com/pricing | Free / Pro $39 / Business $99 / Business+ $134 / Enterprise; download caps 5/10/50/100; clones in private beta |
| 3 | ElevenLabs case study | https://elevenlabs.io/blog/creatorkit | per-line emotion detection, one Professional Voice Clone per emotion, +16% conversion (vendor claim) |
| 4 | Homepage | https://creatorkit.com | AI video agent: link/brief -> video |
| 5 | AI Actors page | https://creatorkit.com/ai-actors | stock actor library |
| 6 | Third-party listings | https://www.stork.ai/en/creatorkit , https://www.getapp.co.uk/software/2118099/creatorkit | feature summaries, lower confidence |

## Core loop

Upload one photo + record/clone voice, type a script, get a lip-synced, emotion-matched talking video of "you" in under ~2 minutes.

## Screens (inferred from public pages — confidence medium; no account used)

| ID | screen | route / how to reach | purpose | key components | states seen |
| --- | --- | --- | --- | --- | --- |
| S01 | Landing / sign up | / | pitch, start free trial | hero, CTA, auth modal | filled |
| S02 | Dashboard / projects | /app | list videos, start new | video grid, quota meter, New button | empty, filled |
| S03 | Create clone: photo | /clones/new | upload one image | dropzone, face-check preview | empty, uploading, error (no face) |
| S04 | Create clone: voice | /clones/new/voice | record or upload voice, or pick library voice | recorder, waveform, voice picker, consent checkbox | empty, recording, processing, error |
| S05 | Actor / clone library | /actors | pick own clone or stock AI actor | card grid, filters, preview player | filled, locked (plan) |
| S06 | Script editor | /videos/new | write script or generate from URL/brief | textarea, per-line emotion chips, language select, AI script button | empty, filled, generating |
| S07 | Scene & format | /videos/new/scene | background/scene, aspect ratio | ratio toggle (1:1, 9:16, 16:9), scene picker | filled |
| S08 | Render progress | /videos/:id | queue + progress | progress bar, ETA | queued, rendering, failed |
| S09 | Result / export | /videos/:id | preview, download MP4, variations | player, Download, Make variation, Translate | done, watermark (free) |
| S10 | Pricing / billing | /pricing, /settings/billing | plans, upgrade | plan cards, Stripe checkout | free, paid, over-quota |
| S11 | Settings / privacy | /settings | delete clone/footage, account | danger zone | filled |

## Flows

```
F01 Create my clone
    S03 upload photo -> S04 record 30-60s voice + consent -> clone ready in S05
    happy path clicks: ~5
    edge: photo has no/multiple faces, low-res photo, noisy audio, voice too short, no consent

F02 Make a talking video
    S05 pick clone -> S06 script (emotion auto-tagged per line) -> S07 format -> S08 render -> S09 download
    happy path clicks: ~6 (number to beat: 4)
    edge: script over plan length, unsupported language, render fails, quota hit

F03 Script from a link
    S06 paste URL/brief -> AI drafts ad script -> edit -> F02
    edge: URL unreadable, paywalled page

F04 Variations / translate
    S09 Make variation (new hook / language / background) -> S08 -> S09

F05 Upgrade
    S09 watermark or S02 quota hit -> S10 -> Stripe -> back to S09 clean export
```

## Components

| component | variants | states | used on |
| --- | --- | --- | --- |
| Button | primary, secondary, ghost, danger | default, hover, disabled, loading | all |
| Dropzone | image, audio | empty, dragging, uploading, error | S03, S04 |
| Voice recorder | — | idle, recording, playback, processing | S04 |
| Avatar card | own clone, stock actor, locked | default, selected, hover-preview | S05 |
| Script line row | with emotion chip | neutral/excited/curious/calm/serious | S06 |
| Aspect toggle | 1:1, 9:16, 16:9 | selected | S07 |
| Progress bar | determinate, indeterminate | queued, running, failed | S08 |
| Video player | preview, result | loading, playing, error | S05, S09 |
| Quota meter | — | ok, near limit, over | S02, S10 |
| Toast | success, error | — | all |

## Inferred data model

```
User        id, email, plan, videos_used_this_period, created_at
            evidence: pricing download caps; confidence: high
Clone       id, user_id, name, photo_url, voice_id, status (processing|ready|failed),
            consent_at, is_private
            evidence: S03/S04, "private brand-locked avatar", "raw footage deleted"; confidence: high
Actor       id, name, photo_url, voice_id, tier (standard|premium)   -- stock library
            evidence: /ai-actors, pricing "premium AI actors"; confidence: medium
Voice       id, provider (elevenlabs|local), emotion (neutral|excited|calm|...), language
            evidence: ElevenLabs case study (one clone per emotion); confidence: high
Video       id, user_id, clone_id|actor_id, script, aspect, language, scene,
            status (queued|rendering|done|failed), mp4_url, watermark, duration_s
            evidence: S06-S09, pricing; confidence: high
ScriptLine  id, video_id, idx, text, emotion, audio_url
            evidence: "identifies intended emotion for each line"; confidence: medium
Subscription user_id, stripe_customer_id, plan, period_end    confidence: guess
```

Relationships: User 1-n Clone, User 1-n Video, Clone/Actor 1-n Video, Video 1-n ScriptLine, Clone 1-n Voice (per emotion).

## Engine (how the clone does it, free/open-source first)

| step | free / open-source option | paid fallback |
| --- | --- | --- |
| Voice clone + TTS | Chatterbox (Resemble AI, MIT, has emotion/exaggeration control), F5-TTS | ElevenLabs (connected in this session; uses credits) |
| Emotion per line | Claude tags each line -> TTS emotion params | — |
| Photo -> talking video | LivePortrait / SadTalker / Hallo / EchoMimic (lip-sync from one photo) | HiggsField, HeyGen |
| Lip-sync polish | LatentSync / MuseTalk | — |
| Compose, captions, ratios | FFmpeg + Whisper captions | — |

Licences must be checked per model before selling (some research models are non-commercial). Needs a GPU (free tier: Google Colab / Kaggle / Hugging Face Spaces ZeroGPU; paid: Modal/RunPod ~cents per video).

## Feature matrix

See `features.csv`. Must: 12, should: 9, could: 6, skip: 4.

## Out of scope (cannot or should not be cloned)

- Their stock AI actors (real people licensed to CreatorKit) — build our own actors from consenting people or synthetic faces.
- CreatorKit's name, logo, copy, the "Emotive AI Actors" branding.
- ElevenLabs partnership terms / their custom per-emotion voice library.
- Done-for-you services and their customers/reviews.

## Size

Screens 11, flows 5, entities 7. Hard parts: (1) single-photo lip-sync quality at ~2 min render on a free/cheap GPU, (2) emotion-consistent voice cloning, (3) GPU job queue + storage + per-video billing. Size: M for a personal tool (2-3 weeks), L for a sellable SaaS.
