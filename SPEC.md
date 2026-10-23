# Spec: furniture-expert skill v1.0.0

Status: complete, all questions answered, awaiting approval (2026-10-23). This file and `tasks/` are working material: the last task deletes
them, because the package validator rejects them in a release tree.

## Objective

Build `furniture-expert`, an Agent Skill and Claude Code plugin for an online furniture store in Ukraine.
It copies the structure, safety model and quality bar of
[dmitriy990/textile-expert-skills](https://github.com/dmitriy990/textile-expert-skills) v1.0.0, but its
content, data, checks and calculator are about furniture.

**User.** The owner or manager of an online furniture store in Ukraine. The store mostly resells Ukrainian
factories, holding stock or using dropship, and imports some lines from Poland and China. The shop runs
on Horoshop. The owner talks to Claude in Russian or Ukrainian. Customers read Ukrainian.

**Store terms the skill must use (as of 23.10.2026):**

- The customer pays for delivery, lifting to the floor and assembly as separate services.
- Exception: the store pays for delivery, and only delivery, on orders delivered within Kyiv whose goods
  total is 19 000 UAH or more (exactly 19 000 qualifies). The goods total excludes paid services. Lifting
  and assembly stay paid by the customer on these orders too.
- Some manufacturers forbid selling below their recommended retail price (RRP/МРЦ). The project config
  lists them by name, and the restriction applies only to them.
- Imports come from Poland (EU, zero duty under the free trade area only with proof of EU origin; goods
  made in Asia and sold through Polish distributors are not of EU origin) and from China (regular duty
  rate, confirmed with a broker).

**Product groups in v1.0.0, all four:**

| Group | Typical items | What the skill must know |
|---|---|---|
| Upholstered | sofas, corner sofas, armchairs, pouffes | frame (solid wood, plywood, chipboard, metal), seat base (zig-zag springs, Bonnel, pocket, belts), foam (PPU density kg/m³, HR), transformation mechanisms, upholstery fabric (velour, chenille, rogozhka, microfibre; Martindale cycles), genuine leather vs eco-leather (PU/PVC) |
| Case furniture | wardrobes, sliding-door wardrobes, chests, beds, shelving, kitchens from modules | ДСП/ЛДСП, МДФ, ДВП/HDF, plywood, solid wood, veneer; facades (film, enamel, acrylic, CPL/HPL); edging (PVC/ABS 0.4/2 mm); fittings (Blum, Hettich, GTV and others); formaldehyde emission classes (E1, E0.5, CARB P2) |
| Mattresses and bed bases | spring and springless mattresses, toppers, slatted bases | Bonnel vs pocket (springs per m² or per berth), foams, natural vs synthetic latex, coconut coir, height, firmness, the "orthopaedic" claim |
| Tables, chairs, office, outdoor | dining sets, office chairs, garden furniture | tabletop materials, office chair load and gas-lift class, outdoor materials (poly-rattan, aluminium, teak, HPL), UV resistance |

**User stories (acceptance at the behaviour level, each one becomes eval cases):**

1. The owner pastes a supplier's spec and asks for a product card. The skill writes it in Ukrainian with
   dimensions W×D×H in cm, materials listed per element (body, facade, frame, filling, upholstery), and no
   unprovable claims. Where data is missing, it lists what it needs.
2. The owner asks what the retail price of a factory sofa should be. The skill runs the calculator
   (supplier price, VAT status, delivery to the warehouse or dropship fee, the expected cost of free Kyiv
   delivery when the price is 19 000 UAH or more, damage and returns, payment fees, margin), lists its
   assumptions, and compares the result with the factory's recommended retail price (RRP/МРЦ).
3. The owner asks what an imported container of chairs from China, or a truckload of chests from Poland,
   really costs. The calculator allocates freight by volume (m³), adds duty, VAT, broker and inland
   delivery, and allows for damage. For Polish goods the skill asks for proof of EU origin before it uses
   a zero duty rate.
4. A price list goes to the shop. The hooks block a price below cost. They ask about a price below RRP
   for a manufacturer that forbids it, a 50 % "discount" or an extra zero.
5. A public text contains the dealer price, the factory's name as a supplier, or "solid wood" for an MDF
   facade. The hooks block it.
6. A customer complains about a scratched facade after delivery, or wants to return a sofa ordered
   online. The skill classifies the case and replies in Ukrainian. Any legal point is dated and sourced.

**Success** means the package passes its own validator and tests in CI. The eval cases pass when a person
judges them. Nothing textile-specific is left in the package.

## Tech Stack

Same as the template, with no new dependencies:

- Python 3.9 to 3.13, standard library only for everything that ships (hooks and scripts).
- PyYAML, used only by the validator for a second frontmatter parse and installed in CI.
- Claude Code plugin format: `.claude-plugin/plugin.json` and `marketplace.json`, with skill hooks
  declared in the `SKILL.md` frontmatter.
- GitHub Actions: one workflow, matrix 3.9 / 3.12 / 3.13.

## Commands

```bash
python3 scripts/validate_package.py              # package checks (exit 0 = all pass)
python3 scripts/validate_package.py --self-test  # proves the validator fails on broken copies
python3 scripts/test_hooks.py                    # hooks + calculator tests (add -v for detail)
pip install pyyaml                               # once, to enable the validator's real YAML parse

# Hooks and calculator by hand (from the repo root)
python3 -I hooks/lint_content.py --file card.md [--internal] [--json]
python3 -I hooks/price_guard.py --csv prices.csv
echo '{"last_assistant_message":"..."}' | python3 -I hooks/stop_check.py
python3 -I scripts/landed_cost.py --mode local --supplier-price 18500 --supplier-vat included --inbound-uah 600 \
    --damage-pct 2 --fee-pct 2 --kyiv-delivery-uah 900 --kyiv-share-pct 40 --margin-pct 30 --rrp 27900
python3 -I scripts/landed_cost.py --mode import --goods 42 --qty 360 --fx 41.5 --unit-cbm 0.18 \
    --freight-per-cbm 95 --duty-pct 10 --broker-uah 12000 --inland-uah 18000 --damage-pct 3 --margin-pct 35

# Leftover check (must print nothing)
grep -rniE 'textile|текстил' --exclude-dir=.git .
```

Calculator flags as implemented in T7–T8; `--help` lists them all.

## Project Structure

The template's layout, with the textile-specific files renamed and one reference added:

```txt
SKILL.md                         skill: base rules R1–R9, workflows W-A…W-G, routing table, manual checks,
                                 NEVER list, response format, hooks block in frontmatter
references/
  materials-and-construction.md  boards, solid wood, veneer, facades, edging, fittings, emissions, metal,
                                 outdoor materials; supplier vocabulary (PL/EN → UA, including the English
                                 terms Chinese suppliers use)
  upholstery-and-mattresses.md   frames, seat bases, foams, mechanisms, upholstery fabrics, leather vs
                                 eco-leather, mattresses and bases
  suppliers-and-origins.md       Ukrainian factories (dealer terms, RRP, stock vs dropship, lead times),
                                 imports from Poland and China (origin, logistics, MOQ, payment),
                                 supplier checklist
  quality-control.md             acceptance, transport damage, assembly check, test standards, certificates,
                                 claims to supplier and from customers
  ukraine-legal.md               labelling and product information, returns, warranty, distance selling,
                                 import duty/VAT/origin, advertising (all dated, all sourced)
  economics-and-pricing.md       local resale and import unit economics, RRP, volumetric freight, last mile,
                                 lifting and assembly, damage and returns, stock vs dropship
  content-and-seo.md             product card template, standard sizes, delivery/lifting/assembly terms,
                                 SEO, customer reply templates
  hooks.md                       what the hooks check, configuration, exceptions, manual run
data/
  config.json                    hook defaults (template keys + rrp_enforced_brands, empty by default)
  materials.json                 material dictionary: tokens in uk/ru/en/pl, family, naming rules
  product_specs.json             typical ranges per measurable parameter and product type
hooks/
  lint_content.py                PostToolUse: checks written content
  price_guard.py                 PreToolUse: checks price files and shop imports
  stop_check.py                  Stop: legal dating and calculation assumptions
scripts/
  landed_cost.py                 unit cost and price: --mode local | import
  test_hooks.py                  unittest suite, hooks run as subprocesses
  validate_package.py            package validator + --self-test
evals/
  cases.json                     ≥ 12 synthetic behavioural cases
  JUDGE.md                       how to run and judge them by hand
.claude-plugin/                  plugin.json (furniture-expert), marketplace.json (ivatech-furniture)
.github/workflows/validate.yml   CI
README.md, README.uk.md, LICENSE (MIT), .gitignore
SPEC.md, tasks/                  working files, deleted in the last task
```

Names derived from the template: skill `furniture-expert`, marketplace `ivatech-furniture`, header line
`# Furniture Expert — <role> — v1.0.0 (<date>)`, project config `<project>/.claude/furniture-expert.json`,
markers `furniture-expert:ok`, `furniture-expert:internal`, `furniture-expert:lang=ru`, debug variable
`FURNITURE_EXPERT_DEBUG`.

## Behaviour of the checks

**`lint_content` (after Write/Edit/MultiEdit of .md .markdown .txt .html .htm .csv .tsv .xml).** The
textile checks for composition, GSM and washing are replaced with these:

| Severity | Check |
|---|---|
| ERROR | Procurement leak in public text: dealer, purchase or supplier price next to a number ("дилерська ціна", "вхідна ціна", "закупівельна", "знижка дилера"), cost and margin with figures, Alibaba/1688 links, `confidential_terms`; cost or supplier columns in a public CSV feed. Hardened as in the template: entities, tags inside words, invisible characters, comments and attributes |
| ERROR | Dimension unit error: a single furniture dimension in cm far outside physical limits, e.g. `2000×900×750 см` (looks like mm) |
| ERROR | A measurable parameter far outside its range (< 0.6 × min or > 1.8 × max from `product_specs.json`): foam density kg/m³, Martindale cycles, board thickness mm, springs per m², mattress height and so on |
| ERROR | Material contradiction in one block: an element made of ДСП/МДФ/ДВП called "масив"/"натуральне дерево"/"solid wood"; eco-leather/PU/PVC called "натуральна шкіра" |
| WARN | Parameter outside the typical range; unproven claims ("ортопедичний", "анатомічний", "гіпоалергенний", "антибактеріальний", "екологічно чистий", "без формальдегіду"); emission or certificate claims (E0/E0.5/E1, CARB, FSC, Greenguard, OEKO-TEX) without a document; origin claims ("Made in Poland", "Made in EU", "польські меблі", "європейська якість"); Russian words in Ukrainian text, with a furniture-specific word list |
| Kept as is | `PARTIAL`, `SCAN_FAILED`, internal-file detection by name tokens and marker, skip list, size and time limits, output sanitising |

**`price_guard`** stays as in the template (deny: negative, NaN/inf, below cost; ask: zero, unreadable,
margin under threshold, ≥ 50 % discount, outlier against the batch median, unparseable price CSV), with one
addition: a per-manufacturer RRP check.

- The project config `<project>/.claude/furniture-expert.json` holds `rrp_enforced_brands`, a list of
  manufacturer names, for example `["Фабрика А", "Brand B"]`. The shipped default is an empty list, so
  the check is off until the owner names the restricted manufacturers.
- For a row whose manufacturer is on the list, a price below its RRP is `ask`. Rows from other
  manufacturers and rows with no RRP value are not checked.
- Names are matched case-insensitively with whitespace normalised. The manufacturer column is recognised as
  `brand`, `manufacturer`, `vendor`, `producer`, `виробник`, `бренд`, `фабрика`, `producent`, `marka` and
  variants. The RRP column is recognised as `rrp`, `мрц`, `рекомендована ціна` and variants. The same keys
  are read from Horoshop MCP import records.
- If the list is not empty and the data has an RRP column but no manufacturer column, the hook cannot tell
  which rows are restricted. It asks once for the whole batch instead of passing it silently.
- The config value is sanitised like `confidential_terms`: strings only, with limits on count and length.

The Horoshop MCP matcher is unchanged.

**`stop_check`** works as before but for furniture topics. It wants a date and a source for answers that
touch three or more legal, customs or tax topics. It wants assumptions for any cost answer, and the
assumption words now include кубатура/м³, доставка, підйом, складання, пошкодження and повернення.

**`landed_cost.py`** has two modes:

- `local`: supplier price in UAH with its VAT status (`--supplier-vat included|on-top|none`), the store's VAT status, delivery to the warehouse or
  a dropship fee, damage and returns %, payment or marketplace fee %, target margin. Delivery, lifting
  and assembly are paid by the customer, so they are not in the cost by default. The one exception is
  free Kyiv delivery. When the retail price is at or above the threshold (`--free-delivery-from`, default
  19 000 UAH), the cost includes the expected delivery cost: Kyiv delivery cost × share of orders
  delivered in Kyiv. Both are inputs. The calculator works per item, so it uses the item's own price as
  the test. An item below 19 000 UAH can still ship in a qualifying order, such as chairs bought with a
  table. For such items the owner can give the share of their sales that ship free in Kyiv
  (`--free-delivery-share-pct`), which replaces the price test. Lifting and assembly never enter the cost.
  Output: unit cost, net and retail price, achieved margin at a given retail price, gap to RRP.
- `import`: the template's formula (customs value, duty, import VAT as a cost for non-payers, broker,
  inland, bank, QC, losses). Freight is given per shipment or per m³ with `--unit-cbm`, which covers a
  truck from Poland and a container from China. Packaging and damage allowance are included. The duty rate
  is always an input, never a built-in default.

Both modes print every assumption and a "5–10 % worse" scenario hint, and validate inputs as the template
does.

## Code Style

Same as the template: stdlib only, fail-open, comments and messages to the user in Ukrainian, safe
reading of anything that comes from the project, short snippets only in hook output.

```python
def main():
    if len(sys.argv) > 1:
        return cli_main(sys.argv[1:])
    try:
        return hook_main()
    except Exception:
        if os.environ.get("FURNITURE_EXPERT_DEBUG"):
            traceback.print_exc()
        return 0  # fail-open
```

- Hook messages: `furniture-expert: ERROR [CODE] <коротко, українською>`, codes in UPPER_SNAKE
  (`DIM_UNIT`, `SPEC_RANGE`, `MAT_SOLID_WOOD`, `MAT_LEATHER`, `LEAK_PRICE`…).
- References are in Russian, the author's working language, as in the template. Anything for customers is
  in Ukrainian. The README is in English with a short `README.uk.md`.
- Legal statements in references: "по состоянию на ДД.ММ.ГГГГ" plus a primary source link. No figures
  without a source; market benchmarks are labelled "ориентир".

## Testing Strategy

- **Unit and behaviour tests**, `scripts/test_hooks.py` with `unittest`. Every hook runs as a subprocess
  with JSON on stdin, exactly as Claude Code runs it. The template's hardening suites (config, output
  sanitising, entity bombs, markup leaks, UTF-8 stdin, fail-open, shipped hook wrapper) are kept and
  re-pointed. The textile suites (composition, density, claims) are replaced with furniture ones: at least
  one positive and one negative test for each ERROR and WARN code in the table above, the RRP check, and
  both calculator modes with numbers checked against a hand calculation.
- **Package validation**, `scripts/validate_package.py`. Same checks and budgets as the template (SKILL
  body ≤ 1500 words, SKILL.md ≤ 25 000 bytes, each reference ≤ 2500 words / 32 000 bytes, SKILL plus the
  largest reference ≤ 4200 words, all references ≤ 11 000 words; forbidden modules and calls in shipped
  code; no secrets, e-mails or dev files; no AI-attribution commit trailers). Names, the reference list,
  data files, config keys and eval categories are updated. `--self-test` must still prove every check
  can fail.
- **Behavioural evals**, `evals/cases.json`, judged by hand per `evals/JUDGE.md`. At least 12 cases. They
  cover all four product groups, resale and both import routes (Poland with and without proof of EU
  origin, China), the per-manufacturer RRP rule, the Kyiv delivery exception, and every category:
  `materials`, `dimensions`, `origin_claims`, `legal_dating`, `confidentiality`, `landed_cost`,
  `price_sanity`, `language`, `unsupported_claims`, `routing`, `missing_data`, `dealer_terms`.
- **CI**: the workflow runs all three commands on 3.9, 3.12 and 3.13.

## Boundaries

- **Always:** stdlib only and offline in shipped code; fail-open hooks run with `python3 -I`; every legal,
  customs or tax statement dated and sourced, researched at implementation time; calculations through the
  script; run the validator, its self-test and the tests before every commit; commit messages without
  Co-Authored-By or "Generated with Claude" lines; keep the template's security hardening.
- **Ask first:** adding a dependency; adding or changing hook events or matchers beyond the template;
  changing size budgets; adding a reference beyond the eight listed; tagging a release or opening a
  PR; any change to the textile repo. Creating `main` from the release commit is already agreed.
- **Never:** network, process, eval or disk-write calls in hooks and scripts; duty rates, law numbers or
  lists of non-returnable goods "from memory"; textile content left in place because it "probably
  applies"; secrets, real e-mails or absolute user paths in the repo; SPEC.md or `tasks/` in the release
  tree.

## Success Criteria

1. `python3 scripts/validate_package.py` exits 0 on a clean checkout, including the dev-file and
   commit-trailer checks, once the last task has removed SPEC.md and `tasks/`.
2. `python3 scripts/validate_package.py --self-test` exits 0.
3. `python3 scripts/test_hooks.py` passes, and CI is green on 3.9, 3.12 and 3.13.
4. `grep -rniE 'textile|текстил' --exclude-dir=.git .` prints nothing.
5. Each of these hook examples gives the stated result in tests:
   - `Розміри: 2000×900×750 см` → ERROR `DIM_UNIT`
   - `Щільність ППУ 350 кг/м³` → ERROR out of range
   - `Фасад МДФ, натуральне дерево` → ERROR `MAT_SOLID_WOOD`
   - `Оббивка: екошкіра (PU), натуральна шкіра` → ERROR `MAT_LEATHER`
   - `Ортопедичний матрац` → WARN
   - public card with `дилерська ціна 12 000 грн` → ERROR
   - CSV row with price below cost → deny
   - CSV row below RRP, manufacturer in `rrp_enforced_brands` → ask
   - the same row, manufacturer not in the list → no output
   - RRP column, no manufacturer column, list not empty → one ask for the batch
6. The `landed_cost.py` example in each mode matches a hand calculation to the kopiyka, and the
   test asserts it. In local mode, a price of 19 000 UAH or more adds the expected Kyiv delivery cost and
   a price just below it does not, unless `--free-delivery-share-pct` is given.
7. `ukraine-legal.md` has an "as of" date and a primary source for every rule. Nothing in it is
   undated.
8. `evals/cases.json` has ≥ 12 well-formed cases meeting the coverage above. The results of a first
   manual run are reported to you and not committed.
9. The version is v1.0.0 and agrees across `SKILL.md`, `plugin.json` and `README.md`.
10. `main` exists on GitHub and points at the release commit. Switching the repository's default branch to
    `main` is done by you in the GitHub settings, since this session has no tool for it.

## Decisions (answered 23.10.2026)

1. Imports: Poland and China.
2. Shop platform: Horoshop. The MCP matcher stays.
3. RRP: enforced per manufacturer via `rrp_enforced_brands`, empty by default.
4. Delivery, lifting and assembly are paid by the customer. Exception: the store pays delivery, and only
   delivery, on Kyiv orders whose goods total is 19 000 UAH or more. Exactly 19 000 qualifies, and paid
   services do not count toward the total.
5. I create `main` from the release commit at the end.

## Open Questions

None.
