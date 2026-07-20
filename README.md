# Cadence

**Do the right thing at the right energy.**

Every to-do app answers *"what do I have to do?"* Cadence answers a harder,
more useful question: **"given how I feel right now, what should I do next?"**

You rate each task on two axes — **Impact** and **Effort** — and tell Cadence
your **current energy** with one tap. A matching engine then surfaces the single
best task for this moment: quick wins when you're drained, big hard bets when
you're sharp — each with a plain-English reason. It's a task manager built
around your energy, not just your deadlines.

Self-contained web app: **zero dependencies, no build step, no backend.** Just
open `index.html`.

## What makes it different

- 🎯 **Energy-aware recommendation engine.** The "Right now, do this" card
  re-ranks your whole list every time your energy changes. Set energy to **Low**
  and it steers you to high-impact/low-effort *quick wins*; set it to **High**
  and it points you at the *big bets* you'd otherwise avoid.
- 🧮 **Transparent fit score.** Every task shows a `fit` number so the ranking
  is never a black box. The formula rewards impact and matches effort to the
  energy you actually have right now.
- ⏱️ **Focus timer with a live progress ring** (15 / 25 / 50 min). Completing a
  session feeds your momentum and streak.
- 🗺️ **Interactive Impact × Effort matrix** — every active task plotted into
  *Quick wins / Big bets / Fill-ins / Time sinks*. Click a dot to focus it.
- 🔥 **Momentum & streaks** — sessions today, all-time, tasks completed, a
  7-day bar chart, and a sparkline of your energy through the day.
- 💾 **Persistence** via `localStorage` — everything survives a refresh.
- 📱 **Responsive**, dark, and animated.

## The recommendation model

Each task has `impact ∈ {1,2,3}` and `effort ∈ {1,2,3}`. Given your current
`energy ∈ {1,2,3}`:

```
gap  = energy − effort            // ≥ 0 means you have the energy for it
fit  = impact × 10 + (2 − gap)    // when gap ≥ 0: reward impact, nudge toward
                                  //   using your energy well
fit  = impact × 10 − 8 × |gap|    // when gap < 0: demote tasks too demanding
                                  //   for your current energy
```

Tasks are ranked by `fit` (ties broken by due date, then age). The result:
the same list recommends *different* tasks depending on how you feel — which is
how people actually work.

| Energy | Recommends | Why |
|--------|-----------|-----|
| **Low** | high impact, light effort | Make progress without burning fuel you don't have |
| **High** | high impact, heavy effort | Spend your peak on the work that only peak-you can do |

## Run it

No install required:

```bash
# Open directly
xdg-open index.html      # Linux
open index.html          # macOS

# …or serve locally
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Project structure

| File         | Purpose                                                      |
|--------------|--------------------------------------------------------------|
| `index.html` | Layout: energy picker, tabs (Now / Tasks / Matrix / Momentum) |
| `styles.css` | Dark theme, ring timer, matrix, responsive design            |
| `app.js`     | Fit engine, focus timer, matrix + momentum rendering, storage |

## Data model

```js
// localStorage key: "cadence.state.v1"
{
  tasks:    [{ id, title, impact, effort, due, done, createdAt }],
  sessions: [timestamp, ...],        // completed focus sessions
  energyLog:[{ t, level }, ...],     // energy readings
  currentEnergy: 1 | 2 | 3,
  focusMin: 25,
  stats: { tasksCompleted }
}
```

A small automation surface is exposed at `window.__cadence`
(`fitScore`, `ranked`, `computeStreak`, `setEnergy`, `completeFocusSession`)
for scripting and testing.

## Possible next steps

- Learn your energy rhythm from history and *suggest* an energy level by time of day
- Auto-schedule a day plan by fitting tasks to a predicted energy curve
- Tags / projects, recurring tasks, and calendar-aware due dates
- A backend + accounts for cross-device sync
