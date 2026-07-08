# 03 · Frontend Design

## Scope, stated harshly

**One page. Read-only. Four hours.** The council cut this phase from 8 h to 4 h to fund the sleep-cycle stretch. The page's real audience is not a user — it's the **camera**: judges will see it for roughly 90 seconds inside a 3-minute video, on a compressed 1080p stream. Every design decision below optimizes for legibility-on-video and zero build risk, in that order.

## Pick

**Single static HTML file, vanilla JS, `fetch` polling every 3 s** against one read-only endpoint. No framework, no build step, no bundler.

Rejected: React/Vite — nothing on this page needs client-side state beyond one polled JSON object, and build tooling is exactly the kind of yak that eats a 4-hour budget. Rejected: server-rendered anything — there is no server; the backend is one Lambda.

Endpoint: `GET {FUNCTION_URL}/status?incident_id=...` → JSON straight from `working_state` + the top-3 matches. One more `GET /health` returning a row count (used live in the node-kill segment).

## Design tokens — house style, tuned for video

The subject is an on-call console at 2 a.m. The design vernacular is the terminal, the pager, the ops room — not a SaaS dashboard.

| Token | Value | Role |
|---|---|---|
| `--ink` | `#12130f` | page background (warm near-black, not pure black — compresses better on video than #000) |
| `--card` | `#1a1b16` | panels |
| `--rule` | `#2c2d26` | hairlines |
| `--text` | `#e9e7dd` | body |
| `--muted` | `#97948a` | secondary |
| `--amber` | `#e6a53f` | attention: confidence badges, the live clock |
| `--teal` | `#5fb8a0` | healthy / resolved / memory hits |
| `--alarm` | `#c9705c` | severity + the killed node, used only when something is actually wrong |

Type: system sans for labels, **monospace for all data** (IDs, timestamps, distances, the clock). On camera, mono data reads as "real system" in a way UI-kit type never does. Minimum body size 16 px; the elapsed clock and confidence badge are the two largest elements on the page.

**Signature element** (the one memorable thing): the **elapsed-incident clock** — top right, large, mono, amber, ticking every second, never stops during the node kill. It's simultaneously the page's identity and the pitch panel's filming requirement: visible proof the take is live and uncut. Everything else stays quiet so this one element carries the moment.

## Layout — one screen, no scrolling during the demo

```
┌────────────────────────────────────────────────────┐
│ ORBITAL · Recall            INC-2094 · ⏱ 00:04:31 │
├──────────────────────────┬─────────────────────────┤
│ ACTIVE INCIDENT          │ MEMORY                  │
│ billing · SEV-2          │ ● INC-1187  0.91  312d  │
│ "Payment webhooks        │ ● INC-0742  0.84   88d  │
│  timing out"             │ ● INC-1650  0.79   41d  │
│ opened 02:14 ICT         │                         │
├──────────────────────────┴─────────────────────────┤
│ DIAGNOSIS                        confidence: HIGH  │
│ Connection-pool exhaustion — matches INC-1187:     │
│ "resolved by rolling back pool-size change".       │
│ Proposed: runbook RB-031 step 2–4.                 │
├────────────────────────────────────────────────────┤
│ EVENT LOG (mono, newest first, max 6 lines)        │
└────────────────────────────────────────────────────┘
```

- **Memory panel** rows: match ID, similarity (2 decimals), age in days — age visibly justifies the decay ranking when two similar scores order "wrong."
- **Confidence badge**: `HIGH` teal / `LOW` amber / `NONE` gray. On `NONE`, the diagnosis panel renders the agent's plain no-match statement — that's AC13 on screen, not just in a log.
- **Event log**: one line per state change (`02:14:07 retrieval hit INC-1187 d=0.09`). During the kill, the log keeps appending — the visible heartbeat.
- Amnesia A/B (AC12): a `?memory=off` query param renders the same page with the memory panel empty and the generic no-context answer — filmed side by side with the normal view. One param, no second page.

## Copy rules

Plain verbs, sentence case, no filler. The interface never apologizes and never sells: "No close match in memory — 0 incidents within threshold" beats "Oops, we couldn't find anything!" An empty memory panel states what it means and what happens next. Labels label; the demo script does the persuading.

## Quality floor (unannounced)

Responsive to 380 px, visible keyboard focus, `prefers-reduced-motion` respected (the clock still ticks — it's information, not decoration). No animation beyond the ticking clock and log appends. If any hour of the four runs over, cut polish in this order: log panel styling → A/B styling → responsive breakpoints. The clock, badge, and memory panel are never cut.
