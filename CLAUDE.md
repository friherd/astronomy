# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Sun, Moon, and planet ephemeris for **Nice, France** — current date/time plus
azimuth, elevation, rise/set, and an observation-window readout for the Sun,
Moon, Mercury, Venus, Jupiter, Saturn, and Mars. Plus live satellite tracking
for ISS, Swift Observatory, and LINK. Delivered as a single self-contained,
live-updating browser app (PWA).

## Layout

```
astronomy/
  index.html            # the entire app — self-contained, live-updating
  manifest.webmanifest  # PWA manifest (name, icons, standalone display)
  sw.js                 # service worker — caches shell for offline use
  icon-180/192/512.png  # app icons
.github/workflows/pages.yml  # deploys astronomy/ to GitHub Pages on push to main
.gitignore
CLAUDE.md
```

The repo root holds git config; all source lives in `astronomy/`. The web app
is deployed at **https://friherd.github.io/astronomy/** and auto-deploys on
every push to `main`.

## Single deliverable

`index.html` is the whole application — all astronomy math, satellite tracking,
and UI in one file. It is intentionally **dependency-free**: no build, no server,
no external libraries. Keep it that way. (A Python CLI port, `france_time.py`,
was removed on 2026-07-17; recover it from git history if ever needed, but the
project is web-only going forward — there is no parity requirement.)

## How to run

- **Web:** open `astronomy/index.html` in a browser (no server, no build, no dependencies).
- **Web over a server** (needed for a secure context — e.g. geolocation — or to
  reach the page from a phone on the LAN): `python3 -m http.server --directory astronomy`.

## What it computes

- **Sun:** NOAA solar position algorithm (`solarPosition`).
- **Moon:** Schlyter's lunar theory with the main perturbation terms and a
  topocentric parallax correction (`moonPosition`).
- **Planets:** Schlyter's heliocentric elements → geocentric via the Sun's
  position → horizontal coordinates, including the Jupiter/Saturn mutual
  perturbations (`planetPosition`, `heliocentric`, `PLANET_ELEMENTS`). Mercury, Venus, Jupiter, Saturn, Mars.
- **Rise/set:** generic elevation scan refined by bisection (`riseSet`); horizon
  is −0.833° for the Sun/Moon, −0.566° for planets.
- **Elongation:** `angSep` computes the great-circle angular separation between a
  body and the Sun from horizontal coordinates; displayed as an "Elong" column.
  Sun row shows `—`.
- **Observation window:** `AZIMUTH_WINDOW` (200–270°) and `ELEVATION_WINDOW`
  (0–16°); a body is "in window" when both hold (`inWindowAt`). `nextWindowPass`
  finds the next entry/exit interval within `WINDOW_HORIZON` (7 days) via a coarse
  scan (`WINDOW_STEP`, 3 min) refined to ~1 s by bisection.
- **Satellites:** Three satellites are tracked: ISS (NORAD 25544, 🛰️),
  Swift Observatory (28485, 🔭), and LINK (69792, 🔗). Each is a config object
  `{ norad, name, sym, cacheKey, minEl, tle, rs }` in `ALL_SATS`. Key functions:
  - `satAzEl(tle, tMs)` — Keplerian + J2 propagator; returns
    `{az, el, alt, subLat, subLon, eci}`. `subLat`/`subLon` are the geocentric
    sub-satellite ground point (from the ECEF vector); `alt` is height in km.
  - `findSatPasses(sat)` — scans `SAT_DAYS` (3) ahead in `SAT_STEP` (30 s) steps,
    bisection-refined; returns up to 5 passes with `{start, end, maxEl, maxAz, win}`.
  - `computeSatRiseSet(sat)` — finds next rise/set within 3 days; refreshed every minute.
  - `fetchAllTLEs()` — fires 3 parallel fetches via `Promise.all` (one per satellite,
    `fetchOneTLE`); saves each to `localStorage` on success. On failure, falls back
    to `loadAllCaches()`.
  - `initAllSats()` — on startup, uses cache if all entries are < 6 hours old;
    otherwise fetches fresh. Auto-refresh every 6 hours.
  - Each satellite appears as a row in the body table (live az/el, altitude sub-label
    via `.alt-sub`, next rise/set), a row in the **sub-satellite ground point** table
    (geocentric lat/lon + altitude; `#geo-rows` in the `.geo-section`), a marker in
    the sky strip when above the horizon, and a dedicated pass panel. A
    **Swift ↔ LINK rendezvous** panel (`#rdv`) appears below the main table,
    updated every second from ECI position vectors: range, range rate
    (closing/opening), altitude gap, along-track phase (lead/lag in ° and
    minutes), inter-plane angle, and phasing drift (LINK's mean-motion advantage
    over Swift, °/day — negative because LINK is the higher/slower one). Below the
    metric grid: an **orbit-shape table** (`orbitShape()` → perigee/apogee alt +
    eccentricity per satellite, so LINK's apsides can be watched converging onto
    Swift's during braking/circularization) and a **closing-trend sparkline** — a
    rolling 14-day history of the daily-minimum range (`updateClosest()` →
    `renderClosing()`, persisted to `localStorage` as `rdv_min_hist`, an array of
    `{date, km}`). Velocities are finite-differenced from position at t and t+1 s;
    orbit normals give the plane angle; Swift's period comes from vis-viva. Note:
    between TLE refreshes these track natural orbital motion, not maneuver progress
    — the daily-minimum trend (sparkline) is the true rendezvous signal.
  - **TLE source:** `https://tle.ivanstanojevic.me/api/tle/{norad}`. Returns JSON
    (`{name, line1, line2}`) with CORS enabled, so the browser fetches directly.
    This replaced CelesTrak, which was dropped because it firewalled the developer's
    IP for excessive requests. Do **not** reintroduce a direct CelesTrak fetch.
    The 6-hour cache limits request volume regardless.
- Location is `LAT`/`LON` (Nice, 43.6808°N 7.2123°E); display timezone is `Europe/Paris`.
  The web app formats Paris time/locale via `Intl` regardless of the viewer.

Angles: azimuth is degrees clockwise from true north; elevation is degrees above
the horizon (negative = below). Accuracy is ~1–2 arcminutes; atmospheric
refraction near the horizon is **not** modelled.

**PWA/offline:** `sw.js` uses a network-first strategy for `index.html` (so
deploys propagate when online) and cache-first for static assets. Cache name
is `sky-v1` — bump it in `sw.js` whenever cached assets change.

## Conventions

- **Propose before implementing.** Describe the approach, the files affected, and
  the tradeoffs, then wait for explicit approval before writing any code — even
  when the direction seems obvious.
- **Test before proposing.** Verify API calls (fetch in `node`, or `curl`), run JS
  in `node`, and sanity-check astronomy against known sky geometry before
  implementing or suggesting changes. Cross-check satellite output against an
  independent tracker (e.g. wheretheiss.at) when practical.
- **Git:** non-trivial features go on a branch, merged into `main` with
  `git merge --no-ff`; the branch is deleted after merging. Small follow-ups
  committed directly to `main`. Commit messages end with the `Co-Authored-By: Claude` trailer.
- Output style: a table, a sky-strip visualization, a "next window pass" panel,
  a sub-satellite ground-point table, satellite pass panels, and a Swift↔LINK
  rendezvous panel.
- **Mobile layout (≤480px):** in the main body table the Elong and Window columns
  are hidden and the azimuth compass sub (`.az-sub`) is hidden; the altitude sub
  (`.alt-sub`) is always visible. The column-hiding rules are scoped
  `table.bodies:not(.geo)` so they do **not** affect the ground-point table (whose
  4th column is Altitude, not Elong). The tables must fit the iPhone 16 Pro viewport
  (393px) without horizontal scroll — keep this constraint when adding columns.
- **Adding a satellite:** add a config object to `ALL_SATS`, add a named
  `refresh<Name>()` function, add a `<div class="passes" id="<name>-passes">` in
  the HTML, and call `makeSatMarker()` for the sky strip. The panel id must be
  `${sat.name.toLowerCase()}-passes`. New satellites automatically get main-table,
  ground-point-table, and sky-strip entries via the existing loops.
