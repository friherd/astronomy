# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Sun, Moon, and planet ephemeris for **Nice, France** — current date/time plus
azimuth, elevation, rise/set, and an observation-window readout for the Sun,
Moon, Venus, Jupiter, Saturn, and Mars.

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
  perturbations (`planet_position`, `PLANET_ELEMENTS`). Venus, Jupiter, Saturn, Mars.
- **Rise/set:** generic elevation scan refined by bisection (`rise_set`); horizon
  is −0.833° for the Sun/Moon, −0.566° for planets.
- **Observation window:** `AZIMUTH_WINDOW` (200–260°) and `ELEVATION_WINDOW`
  (0–16°); a body is "in window" when both hold (`in_window`). `next_window_pass`
  finds the next entry/exit interval within `WINDOW_HORIZON` (7 days) via a coarse
  scan (`WINDOW_STEP`, 3 min) refined to ~1 s by bisection.
- Location is `LATITUDE`/`LONGITUDE` (Nice); display timezone is `Europe/Paris`.
  The web app formats Paris time/locale via `Intl` regardless of the viewer.

Angles: azimuth is degrees clockwise from true north; elevation is degrees above
the horizon (negative = below). Accuracy is ~1–2 arcminutes; atmospheric
refraction near the horizon is **not** modelled.

**PWA/offline:** `sw.js` uses a network-first strategy for `index.html` (so
deploys propagate when online) and cache-first for static assets. Cache name
is `sky-v1` — bump it in `sw.js` whenever cached assets change.

## Conventions

- **Verify numerically, don't assume.** Established practice in this repo is to
  cross-check the JS port against the Python output at a fixed instant (run the
  script body in `node` with the `<script>` extracted), and to sanity-check the
  astronomy against known sky geometry (e.g. Venus must stay within ~47° of the
  Sun; Saturn was the only body threading the window). Do this after changes.
- **Git:** non-trivial features go on a branch, merged into `main` with
  `git merge --no-ff`; the branch is deleted after merging. Small follow-ups have
  been committed directly to `main`. Commit messages end with the
  `Co-Authored-By: Claude` trailer.
- Output style: the CLI prints an aligned Unicode table; the web app mirrors it
  with a table, a sky-strip visualization, and a "next window pass" panel.
