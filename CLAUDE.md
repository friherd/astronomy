# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Sun, Moon, and planet ephemeris for **Nice, France** — current date/time plus
azimuth, elevation, rise/set, and an observation-window readout for the Sun,
Moon, Mercury, Venus, Jupiter, Saturn, and Mars. Plus live satellite tracking
for ISS, Swift Observatory, and LINK.

## Layout

```
astronomy/
  france_time.py        # CLI program (terminal table output)
  index.html            # self-contained browser app (same data, live-updating)
  manifest.webmanifest  # PWA manifest (name, icons, standalone display)
  sw.js                 # service worker — caches shell for offline use
  icon-180/192/512.png  # app icons (generated via Python stdlib)
.github/workflows/pages.yml  # deploys astronomy/ to GitHub Pages on push to main
.gitignore
CLAUDE.md
```

The repo root holds git config; all source lives in `astronomy/`. The web app
is deployed at **https://friherd.github.io/astronomy/** and auto-deploys on
every push to `main`.

## Two deliverables that MUST stay in sync

`france_time.py` (Python) and `index.html` (JavaScript) implement the **same
astronomy in two languages**. Any change to a calculation, the location, or the
observation window must be applied to **both** files, and the two must produce
identical numbers for the same instant. This parity is the core invariant of the
project — don't change one without the other.

**Exception: satellite tracking is web-only.** ISS, Swift, and LINK require live
TLE data from CelesTrak — network-dependent features have no Python equivalent.
Do not add one.

## How to run

- **CLI:** `python3 astronomy/france_time.py` (no dependencies — standard library only).
- **Web:** open `astronomy/index.html` in a browser (no server, no build, no dependencies).
- **Web over a server** (needed for a secure context — e.g. geolocation — or to
  reach the page from a phone on the LAN): `python3 -m http.server --directory astronomy`.

Both are intentionally **dependency-free**. Keep them that way.

## What it computes

- **Sun:** NOAA solar position algorithm (`solar_position`).
- **Moon:** Schlyter's lunar theory with the main perturbation terms and a
  topocentric parallax correction (`moon_position`).
- **Planets:** Schlyter's heliocentric elements → geocentric via the Sun's
  position → horizontal coordinates, including the Jupiter/Saturn mutual
  perturbations (`planet_position`, `PLANET_ELEMENTS`). Mercury, Venus, Jupiter, Saturn, Mars.
- **Rise/set:** generic elevation scan refined by bisection (`rise_set`); horizon
  is −0.833° for the Sun/Moon, −0.566° for planets.
- **Elongation:** `ang_sep`/`angSep` computes the great-circle angular separation between a body and the Sun from horizontal coordinates; displayed as an "Elong" column in both outputs. Sun row shows `—`.
- **Observation window:** `AZIMUTH_WINDOW` (200–270°) and `ELEVATION_WINDOW`
  (0–16°); a body is "in window" when both hold (`in_window`). `next_window_pass`
  finds the next entry/exit interval within `WINDOW_HORIZON` (7 days) via a coarse
  scan (`WINDOW_STEP`, 3 min) refined to ~1 s by bisection.
- **Satellites (web-only):** Three satellites are tracked: ISS (NORAD 25544, 🛰️),
  Swift Observatory (28485, 🔭), and LINK (69793, 🔗). Each is a config object
  `{ norad, name, sym, cacheKey, minEl, tle, rs }` in `ALL_SATS`. Key functions:
  - `satAzEl(tle, tMs)` — Keplerian + J2 propagator; returns `{az, el, alt, eci}`.
  - `findSatPasses(sat)` — scans `SAT_DAYS` (3) ahead in `SAT_STEP` (30 s) steps,
    bisection-refined; returns up to 5 passes with `{start, end, maxEl, maxAz, win}`.
  - `computeSatRiseSet(sat)` — finds next rise/set within 3 days; refreshed every minute.
  - `fetchAllTLEs()` — fires 3 parallel fetches via `Promise.all`; saves each to
    `localStorage` on success. On failure, falls back to `loadAllCaches()`.
  - `initAllSats()` — on startup, uses cache if all entries are < 6 hours old;
    otherwise fetches fresh. Auto-refresh every 6 hours.
  - Each satellite appears as a row in the body table (live az/el, altitude sub-label
    via `.alt-sub`, next rise/set), a marker in the sky strip when above the horizon,
    and a dedicated pass panel. A `🔭 Swift ↔ 🔗 LINK: N km apart` distance line
    appears below the table, updated every second from ECI position vectors.
  - TLE URL: `celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE`.
    **CelesTrak blocks IPs for excessive requests.** Always test API calls with
    `curl` before implementing. The 6-hour cache exists specifically to avoid bans.
- Location is `LAT`/`LON` (Nice, 43.6808°N 7.2123°E); display timezone is `Europe/Paris`.
  The web app formats Paris time/locale via `Intl` regardless of the viewer.

Angles: azimuth is degrees clockwise from true north; elevation is degrees above
the horizon (negative = below). Accuracy is ~1–2 arcminutes; atmospheric
refraction near the horizon is **not** modelled.

**PWA/offline:** `sw.js` uses a network-first strategy for `index.html` (so
deploys propagate when online) and cache-first for static assets. Cache name
is `sky-v1` — bump it in `sw.js` whenever cached assets change.

## Conventions

- **Test before proposing.** Verify API calls with `curl`, run JS in `node`, and
  sanity-check astronomy against known sky geometry before implementing or suggesting changes.
- **Verify numerically.** Cross-check the JS port against the Python output at a
  fixed instant (run the script body in `node` with the `<script>` extracted).
- **Git:** non-trivial features go on a branch, merged into `main` with
  `git merge --no-ff`; the branch is deleted after merging. Small follow-ups
  committed directly to `main`. Commit messages end with the `Co-Authored-By: Claude` trailer.
- Output style: the CLI prints an aligned Unicode table; the web app mirrors it
  with a table, a sky-strip visualization, a "next window pass" panel, satellite
  pass panels, and a Swift↔LINK separation distance line.
- **Mobile layout (≤480px):** the Elong and Window columns are hidden; azimuth
  compass sub (`.az-sub`) is hidden; altitude sub (`.alt-sub`) is always visible.
  The table must fit the iPhone 16 Pro viewport (393px) without horizontal scroll —
  keep this constraint when adding columns.
- **Adding a satellite:** add a config object to `ALL_SATS`, add a named
  `refresh<Name>()` function, add a `<div class="passes" id="<name>-passes">` in
  the HTML, and call `makeSatMarker()` for the sky strip. The panel id must be
  `${sat.name.toLowerCase()}-passes`.
