# Furniture Expert

`furniture-expert` is an Agent Skill for running an online furniture store in Ukraine that resells Ukrainian factories, from stock or by dropship, and imports some lines from Poland and China. It works like a furniture technologist and a commercial director in one: boards, solid wood and veneer, fittings, upholstery and mattresses, dealer terms and recommended retail prices, landed cost and price, quality control and claims, product cards and SEO in Ukrainian, returns, warranty and import rules. It insists on dimensions and materials per element, dates every legal statement, keeps procurement data out of public text, and calculates prices with a script instead of in its head. To install it in Claude Code:

```bash
claude plugin marketplace add dmitriy990/furniture-expert-skills
```

```bash
claude plugin install furniture-expert@ivatech-furniture
```

Then ask in plain language. Claude loads the skill when the task is about furniture, and you can also invoke it by name:

```txt
Write a product card for this corner sofa: pine and plywood frame, foam 35 kg/m³, velour 50,000 Martindale, 280×180×90 cm
Price a factory sofa: 18,500 UAH with VAT, we are not a VAT payer, 30 % margin, RRP 27,900 UAH
What will 360 chairs from China really cost us at 0.18 m³ each and 95 USD per m³?
Check this price list before I upload it to the shop
```

| Task | What the skill does |
|---|---|
| **Product cards and feeds** | Ukrainian cards from a template, dimensions W×D×H in cm, materials per element, no "natural wood" for MDF, no "genuine leather" for eco-leather, no unproven claims |
| **Suppliers and channels** | Ukrainian factories and dealer terms, stock versus dropship, Poland and the EU origin trap, China MOQ, lead times and inspection |
| **Cost and price** | Runs `scripts/landed_cost.py` for factory resale or imports, freight per m³, fees, free Kyiv delivery from 19,000 UAH, the gap to RRP, a worse-case scenario |
| **Quality control** | Acceptance with a test assembly, transport damage, EN standards as a guide, how to verify certificates and emission classes, claims |
| **Legal and customs notes** | Short answers dated "станом на …" with a pointer to the primary source |
| **Assortment and customers** | Reorder points, test batches, replies to customers in Ukrainian |

## Requirements

`python3` on the PATH. The skill needs no connector, no account and no network access: its scripts are standard-library Python and run locally. It has no credentials to configure.

## Automatic checks

In Claude Code the skill registers three small hooks when it is invoked, and they stay active for the rest of the session:

| Hook | When | What it checks |
|---|---|---|
| `lint_content` | after a file is written | board called solid wood, eco-leather called genuine leather, millimetres written as centimetres, foam density, board thickness, Martindale, springs per m² and mattress height against typical ranges, unproven and origin claims, dealer prices and supplier names in public text, Russian words in Ukrainian text |
| `price_guard` | before a price file or a shop import is written | negative price, price below cost, margin under the threshold, a "discount" of 50 % or more, outliers, a price below RRP for the manufacturers you list |
| `stop_check` | before an answer is finished | legal statements without a date and a source, cost figures without assumptions |

They are local, offline and fail-open: an internal error never blocks your work. Settings go in `<your project>/.claude/furniture-expert.json`, including `rrp_enforced_brands`, the manufacturers whose dealer agreements forbid selling below their recommended retail price. The details, the exceptions and a one-minute check that the hooks run on your machine are in [references/hooks.md](references/hooks.md). To switch them off, run `claude plugin disable furniture-expert`.

Hook registration follows Claude Code's documented behaviour for skills. It has not been observed in a live session by the author, which is why that one-minute check exists. Where hooks do not run, the skill runs the same checks by hand before it gives you a result.

## Other ways to install

**Manual copy**

```bash
git clone https://github.com/dmitriy990/furniture-expert-skills.git
```

```bash
mkdir -p ~/.claude/skills/furniture-expert
```

```bash
cp -R furniture-expert-skills/SKILL.md furniture-expert-skills/references furniture-expert-skills/data furniture-expert-skills/hooks furniture-expert-skills/scripts ~/.claude/skills/furniture-expert/
```

**Claude.ai or Cowork:** copy the same files into a `furniture-expert/` folder, delete the `hooks:` block from the frontmatter of `SKILL.md`, zip the folder and upload it as a custom skill. Hooks do not run there, so the skill follows its manual checks. Whether Claude.ai accepts the `hooks:` block was not tested, which is why it is removed.

This is skill version **v1.0.0 (2026-10-23)**.

## What is in the repo

```txt
SKILL.md                     the skill: rules, working processes, response format, hook registration
references/                  eight reference files: materials, upholstery and mattresses, suppliers, QC,
                             Ukrainian rules, pricing, content and SEO, hooks
data/                        typical ranges for furniture parameters, material dictionary, hook defaults
hooks/                       lint_content.py, price_guard.py, stop_check.py
scripts/landed_cost.py       the cost and price calculator (local resale and import)
scripts/test_hooks.py        tests for the hooks and the calculator
scripts/validate_package.py  required files, manifests, budgets, hook structure, links, privacy
evals/cases.json             synthetic behavioural cases
evals/JUDGE.md               how to run and judge the cases by hand
.claude-plugin/              plugin and marketplace manifests
```

The reference files are written in Russian, the working language of the author. Everything the skill writes for customers is Ukrainian.

The validator, its self-test and the tests run in CI on pushes to `main`, on version tags and on pull requests, and you can run them yourself:

```bash
python3 scripts/validate_package.py
```

```bash
python3 scripts/validate_package.py --self-test
```

```bash
python3 scripts/test_hooks.py
```

The eval cases are not automated. [evals/JUDGE.md](evals/JUDGE.md) explains how to run them against a copy of the skill that does not contain `evals/`.

## Update

- **Users:** `claude plugin update furniture-expert@ivatech-furniture`. Auto-update is off by default; you can switch it on per marketplace in `/plugin`.
- **Maintainers:** a release reaches users only when the version changes. The version lives in `SKILL.md` (`metadata.version` and the version header line) and in `.claude-plugin/plugin.json`; the validator checks that they agree and that this README names the header version. Change all of them, run the validator and the tests, then push and tag `v` plus the version.

## Scope and disclaimer

This is a working reference for the Ukrainian market, not legal, customs or tax advice. Rules about consumer rights, returns, warranty, duty, VAT and origin change, and the legal notes in `references/ukraine-legal.md` are dated and cite their sources. Which consumer law applies depends on martial law at the time you read them. Confirm anything that matters with a lawyer, a customs broker or an accountant, and against the primary source (zakon.rada.gov.ua, customs.gov.ua, tax.gov.ua, dpss.gov.ua) before you publish it or rely on it. These notes have not been reviewed by a lawyer.

## License

MIT, see [LICENSE](LICENSE).
