# TaskFlow

A minimal, Todoist-style **task manager** — the MVP of a high-demand
productivity app. Built as a self-contained web app with **zero
dependencies and no build step**: just open `index.html` in a browser.

## Features (MVP scope)

- ➕ **Add tasks** with a title, priority (Low / Medium / High), and optional due date
- ✅ **Complete / uncomplete** tasks with a single click
- 🗑️ **Delete** tasks
- 🗂️ **Filter views** — Inbox, Today, Active, Completed
- 📊 **Progress bar** showing your completion rate
- 🔴 **Overdue highlighting** for past-due tasks
- 💾 **Persistence** via `localStorage` — your tasks survive refreshes
- 📱 **Responsive** layout for desktop and mobile

## Run it

No install required:

```bash
# Option 1 — open the file directly
open index.html          # macOS
xdg-open index.html      # Linux

# Option 2 — serve locally (recommended)
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Project structure

| File         | Purpose                                  |
|--------------|------------------------------------------|
| `index.html` | Markup and layout                        |
| `styles.css` | Styling and responsive design            |
| `app.js`     | State, persistence, and rendering logic  |

## Data model

Each task is stored as:

```js
{ id, title, priority, due, done, createdAt }
```

State lives in `localStorage` under the key `taskflow.tasks.v1`.

## Possible next steps (beyond MVP)

- Projects / labels for grouping tasks
- Drag-and-drop reordering
- Search and keyboard shortcuts
- Recurring tasks and reminders
- A backend + accounts for cross-device sync
