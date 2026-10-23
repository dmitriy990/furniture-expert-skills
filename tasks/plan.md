# Implementation Plan: furniture-expert skill v1.0.0

Source of truth: `SPEC.md` (complete, 2026-10-23). Tasks: `tasks/todo.md`. Both files are deleted in the
last task.

## Overview

The plan copies `dmitriy990/textile-expert-skills` v1.0.0 into this repo and renames its identity to
`furniture-expert`. It then replaces the textile parts one piece at a time: hooks, data, calculator,
references, `SKILL.md`, evals and README. The validator and tests stay green after every task, so a
broken step shows up at once. Last comes a manual eval run, the cleanup, and the release to `main`.

## Architecture Decisions

- **Copy and adapt the template.** It is not a fork, submodule or shared library. The validator expects a
  self-contained package, and the two skills will change at different speeds.
- **Start green, stay green.** Task 1 produces a renamed template that passes all checks with the textile
  content still in place. Each later task swaps out one part and updates its tests and the validator
  in the same commit. The only check that stays red until the end is the leftover grep for "textile".
- **Lint rules are conservative.** An ERROR fires only on an unambiguous pattern within one block, as in
  the template. Ranges live in `data/product_specs.json`, not in code, so the owner can tune them without
  touching Python. Every new code gets a positive and a negative test.
- **One price-check addition, driven by config.** `rrp_enforced_brands` is a list of strings, sanitised the
  same way as `confidential_terms`. No other config keys are added.
- **The calculator stays one SKU per run.** It keeps the template's input validation and output shape,
  with `--mode local|import`. Freight is per shipment or per m³. The free Kyiv delivery cost uses the
  item's own price as the 19 000 UAH test, unless a share of free-delivery sales is given instead.
- **Legal notes come from primary sources read through Firecrawl.** zakon.rada.gov.ua is blocked from this
  container but readable through `firecrawl_scrape` (checked 23.10.2026). Every rule carries
  "по состоянию на" and a link. When something cannot be confirmed, the note says "не знаю наверняка"
  and points to a broker or a lawyer.
- **Commits:** one commit per task, with no Co-Authored-By or "Generated with Claude" lines.

## Dependency Graph

| Task | Depends on |
|---|---|
| T1 renamed template | — |
| T2 spec ranges + dimensions, T3 materials, T5 RRP, T6 stop_check, T7 import mode, T9 legal | T1 |
| T4 claims/origin/leaks/language | T1 (after T2 and T3, same file) |
| T8 local mode | T7 |
| T10 materials ref, T11 upholstery ref | T2, T3 |
| T12 suppliers ref, T13 QC ref | T9 |
| T14 economics ref | T7, T8 |
| T15 content ref | T4, T9 |
| T16 hooks ref | T2–T6 |
| T17 `SKILL.md` | T2–T16 |
| T18 evals → T19 README → T20 eval run → T21 release | each on the previous |

The reference tasks (T9 to T15) do not depend on each other beyond the table, so their research can run in parallel if wanted.
T17 needs every reference and hook in place, because `SKILL.md` routes to them and describes them.

## Task List

### Phase 1: Foundation
- [ ] T1: Renamed template, green baseline

### Checkpoint 1
- [ ] Export check, self-test and tests pass. No `textile-expert`/`ivatech-textile` strings remain.

### Phase 2: Checks and calculator (highest technical risk first)
- [ ] T2: Product spec ranges and dimension checks
- [ ] T3: Material contradiction checks
- [ ] T4: Furniture claims, origin, leak and language lists

### Checkpoint 2: lint
- [ ] Every lint example from SPEC success criterion 5 behaves as stated. Tests green.

- [ ] T5: Per-manufacturer RRP check in `price_guard`
- [ ] T6: `stop_check` for furniture topics
- [ ] T7: Calculator import mode (m³ freight)
- [ ] T8: Calculator local mode (VAT, dropship, Kyiv free delivery, RRP gap)

### Checkpoint 3: behaviour review with you
- [ ] All tests green, also under Python 3.9 if uv can install it here.
- [ ] I send you sample outputs (lint messages, price-check asks, both calculator modes) and the ranges
      in `data/product_specs.json`. You confirm before content work starts.

### Phase 3: Knowledge (references, Russian)
- [ ] T9: `ukraine-legal.md` from primary sources
- [ ] T10: `materials-and-construction.md`
- [ ] T11: `upholstery-and-mattresses.md`
- [ ] T12: `suppliers-and-origins.md`
- [ ] T13: `quality-control.md`
- [ ] T14: `economics-and-pricing.md`
- [ ] T15: `content-and-seo.md`
- [ ] T16: `hooks.md`

### Checkpoint 4
- [ ] Word budgets pass, all links resolve, every legal statement is dated and sourced.

### Phase 4: Skill and packaging
- [ ] T17: `SKILL.md` rules, workflows, routing, manual checks
- [ ] T18: Eval cases and judge protocol
- [ ] T19: README, README.uk.md, manifests

### Checkpoint 5: package review with you
- [ ] Leftover grep prints nothing. Export check, self-test and tests pass. You review the package.

### Phase 5: Release
- [ ] T20: First manual eval run, fixes, results reported to you
- [ ] T21: Cleanup, release commit, `main`, CI green

## Verification Commands

```bash
# During development: validate the package without the working files (dev-file check would fail otherwise)
D="$SCRATCH/pkg"; rm -rf "$D"; mkdir -p "$D"
git ls-files -co --exclude-standard | grep -vE '^(SPEC\.md|tasks/)' | tar -cf - -T - | tar -xf - -C "$D"
python3 scripts/validate_package.py "$D"
python3 scripts/validate_package.py --self-test
python3 scripts/test_hooks.py
uv run --python 3.9 python scripts/test_hooks.py   # at checkpoints, if the download works here

# Leftover check (the final gate only)
grep -rniE 'textile|текстил' --exclude-dir=.git .

# After T21 (release tree, git mode, includes the commit-message check)
python3 scripts/validate_package.py
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Legal facts are wrong or out of date: returns of furniture, the new consumer law 3153-IX and when it applies, the non-returnable list 1243-2024-п, origin rules for Polish goods, duty on chapter 94 | High | Primary sources through Firecrawl. Every rule dated and linked. No duty rates baked into code. "Не знаю наверняка" plus who to ask when a fact cannot be confirmed. The README disclaimer stays |
| New lint checks raise false alarms on real cards (dimensions, "масив", "шкіра") | High | Same-block rules only, ERROR only for unambiguous cases, a negative test for every code, the ranges reviewed by you at Checkpoint 3, and the `furniture-expert:ok` escape kept |
| `lint_content.py` (832 lines) breaks while being reworked | Med | Three separate tasks (T2 to T4), each keeping the template's hardening suites green |
| Python 3.9 compatibility, since only 3.11 to 3.13 are installed here | Med | Follow the template's idioms (`from __future__ import annotations`, no `match`, no runtime `X \| Y`). Try `uv` with 3.9 at checkpoints; CI on `main` is the final proof |
| Word budgets: 8 references in ≤ 11 000 words, `SKILL.md` body ≤ 1500 | Med | Validator after every reference task; trim tables before prose |
| CI does not run on this branch (the workflow triggers on `main`, tags and PRs) | Low | Local runs at every checkpoint; CI is checked after `main` is pushed in T21 |
| Hook registration from plugin skills not observed live (same as the template) | Low | Keep the one-minute check in `hooks.md` and the manual checks in `SKILL.md` |
| GitHub default branch stays `claude/awesome-fermi-0eqq2s` | Low | You switch it to `main` in the repository settings after T21 |

## Open Questions

None. The ranges in `data/product_specs.json` are market benchmarks I will propose. You review them at
Checkpoint 3.
