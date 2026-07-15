# What's been verified, and where to see it

No automated test suite exists yet -- everything below was verified by
actually running the code against a live ComfyUI server and inspecting real
output (not mocked), during the build session on 2026-07-14/15. This file is
the index; the primary evidence is the **git commit messages**
(`git log`) and the **conversation transcript** where each check happened,
since the checks are ad-hoc shell/curl sessions, not committed test files.

## How to see it

```bash
git log --oneline          # one commit per task/fix, each message
                            # documents exactly what was tested and found
git log -p <hash>           # full diff for any specific fix
```

The three commits and what each one's message documents:

| Commit | What it verified |
|---|---|
| `c1f8cc5` Initial commit: character-forge-v2 scaffold | `pip install -e .` succeeds; a direct Python import of every module (`config`, `schemas`, `stages.concept`, `stages.generate`) resolves with no errors; `forge2 --help` lists exactly the three intended commands. |
| `301fa3d` Seed gtee_dev workspace | `workspace_layout()`/`CharacterCard.load()` resolve correctly against the seeded `character.json`/`hero.png`/`01_hero_candidates/` -- confirmed via a direct Python check, not just "the files exist." |
| `b2044d0` Fix: SystemExit wasn't caught by callback error handling | **Real bug found and fixed.** Verified via two live runs against an intentionally-unreachable ComfyUI port: before the fix, a connectivity failure exited with code 1 and **zero callback POST**; after the fix, the same failure correctly POSTs `{"ok": false, "error": "..."}` to the callback URL. |

## The two most important things verified live (not in a commit, in-session)

1. **A real successful end-to-end generation**, confirmed by actually opening
   the output PNG and visually checking it's the correct character in the
   correct pose (not just checking the file exists or the HTTP status was
   200) -- e.g. `workspace/gtee_dev/generated/gen_09002.png`, a "waving
   hello, office background" render that came back correct on the first
   real successful attempt.
2. **Renders that silently come back corrupted** (solid black, ~3KB instead
   of ~700KB+) despite ComfyUI reporting `"status": "success"` and the
   callback firing `ok: true`. This is real -- it happened multiple times
   during testing, root-caused to low free RAM and separately to ComfyUI's
   own accumulated state after long uptime (see README's Known Issues).
   **The lesson: an `ok: true` callback and a 200 status do NOT prove the
   image is good** -- always spot-check the actual pixel content, which is
   why this file calls that out explicitly rather than letting "the API
   said success" stand in for real verification.

## What is NOT covered

- No automated regression tests (pytest or otherwise) exist for this repo.
- The `concept`/`pick-hero` commands were exercised as part of building the
  original `gtee_dev` character in the sibling `character-forge` project
  (before the v2 trim), not freshly re-verified end-to-end in v2 itself --
  only `generate` (the capability v2 actually adds/changes) got fresh live
  verification here.
- No test coverage for the `lightning` speed profile (only `full` was used
  in all live tests).
