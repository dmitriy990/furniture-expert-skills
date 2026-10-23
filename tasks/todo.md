# Tasks: furniture-expert v1.0.0

Plan: `tasks/plan.md`. Spec: `SPEC.md`. "Export check" = the validator run on a copy without `SPEC.md`
and `tasks/` (command in the plan). Every task ends with the export check, `--self-test`,
`scripts/test_hooks.py` and one commit without AI-attribution trailers.

## Phase 1: Foundation

## Task 1: Renamed template, green baseline

**Description:** Copy every file of textile-expert-skills v1.0.0 (except `.git`) into this repo. Rename the
identity everywhere: skill name, marketplace `ivatech-furniture`, header `# Furniture Expert — …`, hook
fallback paths `~/.claude/skills/furniture-expert`, project config `furniture-expert.json`, markers
`furniture-expert:ok|internal|lang=`, `FURNITURE_EXPERT_DEBUG`, homepage and repository URLs. Content
stays textile for now.

**Acceptance criteria:**
- [ ] Export check, `--self-test` and `test_hooks.py` all pass
- [ ] `grep -rnE 'textile-expert|ivatech-textile|TEXTILE_EXPERT' --exclude-dir=.git .` matches only the
      `SPEC.md`/`tasks/` lines that name the template repo

**Verification:**
- [ ] Commands above; `git diff --stat` shows only renames of identity strings against the template

**Dependencies:** None

**Files likely touched:** all template files (mechanical rename; the one task allowed above 5 files)

**Estimated scope:** L, mechanical

## Checkpoint 1
- [ ] Baseline green and committed

## Phase 2: Checks and calculator

## Task 2: Product spec ranges and dimension checks

**Description:** Replace `data/fabric_specs.json` with `data/product_specs.json`. It holds typical ranges
per parameter and product type: foam density kg/m³, Martindale cycles, board thickness mm, springs per
m², mattress height, seat height and others. In `lint_content.py`, remove the GSM, momme, oz and
thread-count checks and add `SPEC_RANGE` (WARN outside the range, ERROR below 0.6 × min or above
1.8 × max) and `DIM_UNIT` (ERROR for a W×D×H value in cm beyond physical limits). Update the validator's
data checks and self-test mutations.

**Acceptance criteria:**
- [ ] `Розміри: 2000×900×750 см` → ERROR `DIM_UNIT`; `Розміри: 200×90×75 см` → no issue
- [ ] `Щільність ППУ 350 кг/м³` → ERROR; `Щільність ППУ 30 кг/м³` → no issue; a value just outside the
      range → WARN
- [ ] The validator rejects an inverted range and a corrupted `product_specs.json` (self-test)

**Verification:**
- [ ] New test classes in `test_hooks.py` pass; export check and self-test pass

**Dependencies:** T1

**Files likely touched:** `data/product_specs.json` (new), `data/fabric_specs.json` (deleted),
`hooks/lint_content.py`, `scripts/test_hooks.py`, `scripts/validate_package.py`

**Estimated scope:** M

## Task 3: Material contradiction checks

**Description:** Replace `data/fibres.json` with `data/materials.json`, a material dictionary with tokens in
uk/ru/en/pl and families: board, solid wood, veneer, metal, glass, stone, leather, artificial leather,
fabric, foam, plastic, rattan. Remove the composition-sum, bamboo, washing, "silky" and "natural fibre"
checks. Add `MAT_SOLID_WOOD` and `MAT_LEATHER`, both ERROR and both within one block.

**Acceptance criteria:**
- [ ] `Фасад МДФ, натуральне дерево` → ERROR `MAT_SOLID_WOOD`; `Фасад МДФ, шпон дуба` → no issue;
      `Стільниця: масив дуба` → no issue
- [ ] `Оббивка: екошкіра (PU), натуральна шкіра` → ERROR `MAT_LEATHER`; `Оббивка: натуральна шкіра` →
      no issue
- [ ] Validator data checks and self-test updated for `materials.json`

**Verification:**
- [ ] Tests, export check and self-test pass

**Dependencies:** T1

**Files likely touched:** `data/materials.json` (new), `data/fibres.json` (deleted), `hooks/lint_content.py`,
`scripts/test_hooks.py`, `scripts/validate_package.py`

**Estimated scope:** M

## Task 4: Furniture claims, origin, leak and language lists

**Description:** Re-target the lint word lists. Unproven claims become "ортопедичний", "анатомічний",
"гіпоалергенний", "антибактеріальний", "екологічно чистий" and "без формальдегіду". Emission and
certificate claims: E0, E0.5, E1, CARB, FSC, Greenguard, OEKO-TEX. Origin claims: Made in Poland/EU,
"польські меблі", "європейська якість". Leak keywords: дилерська, вхідна, закупівельна ціна, знижка
дилера, Alibaba/1688, plus cost and supplier CSV columns. Russian words: a furniture list (шкаф, стул,
кровать, мебель…). The template's leak hardening stays.

**Acceptance criteria:**
- [ ] `Ортопедичний матрац` → WARN; `Клас емісії E1` without a document → WARN
- [ ] A public card with `дилерська ціна 12 000 грн` → ERROR; the same text in an `_internal` file → no
      leak error
- [ ] `Шкаф-купе` in Ukrainian text → WARN; the markup, entity and comment leak suites still pass

**Verification:**
- [ ] Tests, export check and self-test pass

**Dependencies:** T1 (can follow T2/T3 in the same file; done after them to avoid conflicts)

**Files likely touched:** `hooks/lint_content.py`, `scripts/test_hooks.py`

**Estimated scope:** S

## Checkpoint 2: lint
- [ ] All lint examples from SPEC success criterion 5 pass; full test suite green

## Task 5: Per-manufacturer RRP check in price_guard

**Description:** Add `rrp_enforced_brands` (an empty list) to `data/config.json`. Sanitise it like
`confidential_terms` in every hook that loads the config. Add it to the validator's `CONFIG_KEYS`.
`price_guard` recognises the RRP and manufacturer columns and keys (CSV and Horoshop MCP records) and
asks on a price below RRP for listed manufacturers. It asks once per batch when the list is not empty
and the manufacturer column is missing.

**Acceptance criteria:**
- [ ] Listed manufacturer below RRP → ask; unlisted → no output; no RRP value → no output
- [ ] RRP column without a manufacturer column, list not empty → exactly one ask; list empty → no output
- [ ] Wrong config types (number, dict, a very long list) fall back to an empty list (hardening test)

**Verification:**
- [ ] Tests, export check and self-test pass

**Dependencies:** T1

**Files likely touched:** `data/config.json`, `hooks/price_guard.py`, `hooks/lint_content.py`
(`DEFAULT_CONFIG`), `scripts/test_hooks.py`, `scripts/validate_package.py`

**Estimated scope:** M

## Task 6: stop_check for furniture topics

**Description:** Switch the topic regex from textiles to furniture. Keep the legal patterns: мито, ПДВ,
УКТЗЕД, повернення, гарантія, маркування, походження, EUR.1. Add the assumption words кубатура/м³,
доставка, підйом, складання, пошкодження and повернення. Keep the once-per-answer guard.

**Acceptance criteria:**
- [ ] A long furniture answer with three legal topics and no date → asks for "станом на"; with a date and
      "перевірте" → passes
- [ ] A furniture cost answer without assumption words → asks; a non-furniture answer → passes

**Verification:**
- [ ] Tests pass

**Dependencies:** T1

**Files likely touched:** `hooks/stop_check.py`, `scripts/test_hooks.py`

**Estimated scope:** S

## Task 7: Calculator import mode

**Description:** Restructure `landed_cost.py` around `--mode import|local`. Import mode is the template
formula plus freight per m³ (`--unit-cbm`, `--freight-per-cbm`) as an alternative to `--freight`,
packaging per unit, and the damage allowance. `--duty-pct` becomes required in import mode.

**Acceptance criteria:**
- [ ] A worked example (a China container and a Poland truck) equals a hand calculation to the kopiyka
      in a test
- [ ] Missing `--duty-pct`, or both `--freight` and `--freight-per-cbm` given, ends with a clear error
- [ ] The output lists every assumption and the "5–10 % worse" hint

**Verification:**
- [ ] Tests pass

**Dependencies:** T1

**Files likely touched:** `scripts/landed_cost.py`, `scripts/test_hooks.py`

**Estimated scope:** S

## Task 8: Calculator local mode

**Description:** Local mode takes the supplier price in UAH (`--supplier-vat-included yes|no`), the store's
VAT status, delivery to the warehouse or a dropship fee, damage and returns %, payment or marketplace fee
%, margin, retail price and RRP. Free Kyiv delivery is added when the item price is at least
`--free-delivery-from` (default 19000): `--kyiv-delivery-uah` × `--kyiv-share-pct`.
`--free-delivery-share-pct` replaces the price test. Lifting and assembly never enter the cost.

**Acceptance criteria:**
- [ ] A worked example equals a hand calculation to the kopiyka; VAT payer and non-payer differ as expected
- [ ] Price 19 000 → Kyiv delivery included; 18 999 → not included; 18 999 with the share flag → included
- [ ] The output shows the gap to RRP when `--rrp` is given

**Verification:**
- [ ] Tests pass

**Dependencies:** T7

**Files likely touched:** `scripts/landed_cost.py`, `scripts/test_hooks.py`

**Estimated scope:** S

## Checkpoint 3: behaviour review with you
- [ ] Full suite green, also under Python 3.9 via uv if available
- [ ] Sample outputs and the `product_specs.json` ranges sent to you; your go-ahead before Phase 3

## Phase 3: Knowledge (references in Russian, ≤ 2500 words each)

## Task 9: ukraine-legal.md from primary sources

**Description:** Research and write: product information and labelling for furniture; returns and exchange
under the consumer law in force on the date (3153-IX or 1023-XII, whichever applies), distance selling,
the non-returnable list (1243-2024-п or 172-94-п); warranty and claims; import from Poland (DCFTA, proof
of EU origin, EUR.1 or an invoice declaration) and from China; how to find the duty for chapter 94 and
VAT on import; advertising. Set `legal_as_of` in `config.json`.

**Acceptance criteria:**
- [ ] Every rule has "по состоянию на" and a primary-source link (zakon.rada.gov.ua, customs.gov.ua,
      tax.gov.ua, dpss.gov.ua)
- [ ] No duty rate stated as a number without a dated source; anything not confirmed is marked as such
- [ ] Templates for the returns policy and the delivery terms (with the Kyiv 19 000 UAH rule) are in
      Ukrainian

**Verification:**
- [ ] Export check (budgets, links); sources re-opened while writing

**Dependencies:** T1

**Files likely touched:** `references/ukraine-legal.md`, `data/config.json`

**Estimated scope:** S (research-heavy)

## Task 10: materials-and-construction.md

**Description:** Replace `fabrics-and-fibres.md`. Cover board materials, solid wood and veneer, facades,
edging, fittings, emissions, metal, glass and stone, outdoor materials, and the PL/EN → UA supplier
vocabulary. Update the validator's `REFERENCES` and the `SKILL.md` routing row in the same commit.

**Acceptance criteria:**
- [ ] Terms and ranges agree with `materials.json` and `product_specs.json`
- [ ] The validator's reference list and the `SKILL.md` routing point at the new file; links resolve

**Verification:**
- [ ] Export check and self-test pass

**Dependencies:** T2, T3

**Files likely touched:** `references/materials-and-construction.md` (new),
`references/fabrics-and-fibres.md` (deleted), `scripts/validate_package.py`, `SKILL.md`

**Estimated scope:** S

## Task 11: upholstery-and-mattresses.md

**Description:** A new reference covering frames, seat bases, foams, mechanisms, upholstery fabrics and
Martindale, leather vs eco-leather, mattresses and bases, and care. Add it to the validator's
`REFERENCES` and to the `SKILL.md` routing.

**Acceptance criteria:**
- [ ] Ranges agree with `product_specs.json`; the "orthopaedic" claim is explained as unprovable without
      documents
- [ ] All references together stay ≤ 11 000 words

**Verification:**
- [ ] Export check and self-test pass

**Dependencies:** T2, T3

**Files likely touched:** `references/upholstery-and-mattresses.md` (new), `scripts/validate_package.py`,
`SKILL.md`

**Estimated scope:** S

## Task 12: suppliers-and-origins.md

**Description:** Replace `origins-by-country.md`. Cover Ukrainian factories (dealer agreements, RRP, stock
vs dropship, lead times, defects), Poland (EU origin vs Asian goods via Polish distributors, truck
logistics), China (MOQ, payment, sea and rail, inspection), and the supplier checklist.

**Acceptance criteria:**
- [ ] Origin statements link to `ukraine-legal.md` rather than restating rates
- [ ] Validator reference list and `SKILL.md` routing updated; links resolve

**Verification:**
- [ ] Export check and self-test pass

**Dependencies:** T9

**Files likely touched:** `references/suppliers-and-origins.md` (new), `references/origins-by-country.md`
(deleted), `scripts/validate_package.py`, `SKILL.md`

**Estimated scope:** S

## Task 13: quality-control.md

**Description:** Rewrite for furniture: acceptance of goods from factories and imports, transport damage,
the assembly check, test standards (EN/ДСТУ for seating, storage, beds, mattresses, office chairs,
outdoor), how to verify certificates and emission claims, claims to the supplier and from customers.

**Acceptance criteria:**
- [ ] Each standard is named with its scope, without invented clause numbers
- [ ] The customer-claim flow matches the warranty and returns notes in `ukraine-legal.md`

**Verification:**
- [ ] Export check passes

**Dependencies:** T9

**Files likely touched:** `references/quality-control.md`

**Estimated scope:** XS

## Task 14: economics-and-pricing.md

**Description:** Rewrite for local resale and import: the cost formulas used by the calculator, RRP and
dealer discounts, VAT status, the Kyiv free delivery cost, volumetric freight, damage and returns, stock
vs dropship, working capital and currency risk. It includes worked examples taken from the calculator's
test cases.

**Acceptance criteria:**
- [ ] Formulas match `landed_cost.py` exactly; examples are labelled as illustrative
- [ ] The command examples run as written

**Verification:**
- [ ] Run each command example; export check passes

**Dependencies:** T7, T8

**Files likely touched:** `references/economics-and-pricing.md`

**Estimated scope:** XS

## Task 15: content-and-seo.md

**Description:** Rewrite: a Ukrainian product card template (W×D×H, materials per element, mechanism,
filling, upholstery, load, warranty, assembly, package contents), standard sizes (beds, mattresses,
sofas, tables), the delivery, lifting and assembly terms with the Kyiv rule, SEO and meta, and customer
reply templates (delivery damage, assembly, returns, a warranty claim).

**Acceptance criteria:**
- [ ] `lint_content.py --file` on the card template and each reply template produces no ERROR
- [ ] The delivery terms state that lifting and assembly are paid on all orders, Kyiv included

**Verification:**
- [ ] Run the lint on extracted templates; export check passes

**Dependencies:** T4, T9

**Files likely touched:** `references/content-and-seo.md`

**Estimated scope:** XS

## Task 16: hooks.md

**Description:** Rewrite for the furniture checks: the event table, the ERROR and WARN lists, the RRP
setting with an example `furniture-expert.json`, exceptions, the one-minute live check with a furniture
example, manual runs, and limitations.

**Acceptance criteria:**
- [ ] Every code emitted by the hooks is documented, and every documented code exists (checked by grep)
- [ ] The live-check example triggers the documented message when run by hand

**Verification:**
- [ ] Run the example; export check passes

**Dependencies:** T2–T6

**Files likely touched:** `references/hooks.md`

**Estimated scope:** XS

## Checkpoint 4
- [ ] Budgets and links pass; every legal statement dated and sourced; references read once end to end

## Phase 4: Skill and packaging

## Task 17: SKILL.md

**Description:** Rewrite the description (RU/UK/EN keywords for triggering) and the role header. Rewrite
R1–R9, workflows W-A to W-G (card, supplier choice, cost and price, acceptance and QC, legal, assortment
with stock vs dropship, customer communication and claims), the routing table for 8 references, the
manual checks, the NEVER list and the response format. The hooks block keeps its structure.

**Acceptance criteria:**
- [ ] Body ≤ 1500 words; `SKILL.md` + the largest reference ≤ 4200 words
- [ ] Every path mentioned exists; every hook code and calculator flag mentioned matches the code

**Verification:**
- [ ] Export check and self-test pass

**Dependencies:** T2–T16

**Files likely touched:** `SKILL.md`

**Estimated scope:** S

## Task 18: Eval cases and judge protocol

**Description:** At least 12 cases covering the four product groups, resale, Poland with and without
proof of origin, China, the per-manufacturer RRP rule, the Kyiv delivery exception, and the categories
from the spec. Update the validator's `EVAL_CATEGORIES` and `MIN_EVAL_CASES` (12) and the furniture
wording in `JUDGE.md`.

**Acceptance criteria:**
- [ ] ≥ 12 cases; every category used; every `rule_refs` value exists in `SKILL.md`
- [ ] Figures in requirements come from the calculator output

**Verification:**
- [ ] Export check and self-test pass

**Dependencies:** T17

**Files likely touched:** `evals/cases.json`, `evals/JUDGE.md`, `scripts/validate_package.py`

**Estimated scope:** S

## Task 19: README, README.uk.md, manifests

**Description:** Rewrite both READMEs for the furniture skill (examples, task table, hook table, install,
update, disclaimer). Update the descriptions and keywords in `plugin.json` and `marketplace.json`. Set
the release date in the header and README.

**Acceptance criteria:**
- [ ] The validator's README and manifest checks pass (install commands, version, disclaimer)
- [ ] `grep -rniE 'textile|текстил' --exclude-dir=.git .` prints nothing outside `SPEC.md`/`tasks/`

**Verification:**
- [ ] Export check, self-test, tests and grep

**Dependencies:** T17, T18

**Files likely touched:** `README.md`, `README.uk.md`, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`

**Estimated scope:** S

## Checkpoint 5: package review with you
- [ ] Everything green; you review the package before the eval run and release

## Phase 5: Release

## Task 20: First manual eval run

**Description:** Run every case in a fresh context against a copy of the skill without `evals/`, one
fresh-context subagent per case. Judge each per `JUDGE.md`, re-run failures once, and fix the skill
where two runs out of two fail.

**Acceptance criteria:**
- [ ] A result table per case is sent to you (not committed)
- [ ] Every confirmed defect is fixed or listed with the reason it stays

**Verification:**
- [ ] Fixes pass the export check and tests

**Dependencies:** T19

**Files likely touched:** depends on the findings (`SKILL.md`, references)

**Estimated scope:** M

## Task 21: Cleanup and release

**Description:** Delete `SPEC.md` and `tasks/`. Run the validator in git mode (dev files and commit
messages included). Push the branch, create `main` from the release commit and push it. Watch CI on
`main` until it is green on 3.9, 3.12 and 3.13. Tell you to switch the default branch. Ask you before
tagging `v1.0.0`.

**Acceptance criteria:**
- [ ] `python3 scripts/validate_package.py` passes in the repo itself
- [ ] CI is green on `main`

**Verification:**
- [ ] The validator output and the CI run status on `main`

**Dependencies:** T20

**Files likely touched:** `SPEC.md` and `tasks/` (deleted)

**Estimated scope:** XS
