#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
furniture-expert / lint_content.py  —  PostToolUse-хук (Write|Edit|MultiEdit) и CLI.

Что делает: после записи файла с текстом для магазина (описание товара, статья,
CSV/XML-фид) проверяет его «глазами текстильщика»:
  ERROR  — склад не дає 100 %; «бамбук» як назва волокна; ціна/собівартість/
           постачальник у публічному тексті; щільність, що явно не відповідає тканині.
  WARN   — щільність поза типовим діапазоном; режим прання, шкідливий для волокна;
           «натуральний» при синтетиці; медичні/сертифікаційні заяви без доказів;
           завищений thread count; російська лексика в україномовному тексті.

Принципи безпеки (локально, офлайн):
  * тільки стандартна бібліотека Python, жодних мережевих викликів;
  * вміст файлів НІКУДИ не логується і не зберігається; у відповідь хука потрапляють
    лише короткі фрагменти (≤ 60 символів) для виправлення;
  * fail-open: будь-яка внутрішня помилка → тихий вихід 0 (не блокуємо роботу).

Режими:
  stdin-JSON (як хук):   python3 -I lint_content.py < hook_input.json
  CLI:                   python3 -I lint_content.py --file draft.md [--json] [--public|--internal]
Виняток для рядка: додайте в нього  furniture-expert:ok
Позначка внутрішнього файлу (пропускає перевірки витоку/мови):  furniture-expert:internal
"""
from __future__ import print_function

import html as _html
import json
import math
import os
import re
import stat
import sys
import time
import traceback
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(SKILL_DIR, "data")

MAX_BYTES = 2000000
MAX_BLOCK = 20000    # довжина блока для перевірок (довші ріжуться) — захист від квадратичних випадків
MAX_ISSUES = 200
TIME_BUDGET_S = 6.0  # загальний бюджет часу на блоки; хук має таймаут 15 с
LINT_EXT = {".md", ".markdown", ".txt", ".html", ".htm", ".csv", ".tsv", ".xml"}
MARKUP_EXT = {".html", ".htm", ".xml"}
SKIP_NAMES = {"skill.md", "claude.md", "agents.md", "readme.md", "changelog.md"}
# внутрішній файл — за ТОЧНИМ токеном у назві файлу або в назві його теки (не за підрядком шляху)
INTERNAL_TOKENS = {
    "internal", "private", "confidential", "cost", "costs", "landed", "calc", "calculation", "calculator",
    "supplier", "suppliers", "procurement", "purchase", "purchasing", "margin", "margins",
    "закупівля", "закупка", "закупівельний", "собівартість", "себестоимость", "внутрішній", "внутр",
    "постачальник", "постачальники", "поставщик", "маржа",
}
SKIP_CLAUDE_SUBDIRS = {"skills", "agents", "commands", "plugins", "rules", "hooks"}

DEFAULT_CONFIG = {
    "min_gross_margin_pct": 20,
    "price_outlier_ratio": 30,
    "lint_block_on_error": True,
    "stop_check_enabled": True,
    "legal_as_of": "",
    "confidential_terms": [],
}

# --------------------------------------------------------------------------- utils


def _load_json(path, default, limit=65536):
    """Безпечне читання JSON: лише звичайний файл і не більше `limit` байт, інакше — default.
    Конфіг проєкту приходить із чужого репозиторію: FIFO чи пристрій (/dev/zero) не повинні ні зависати, ні їсти пам'ять."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return default
        with os.fdopen(fd, "rb") as f:
            fd = None
            raw = f.read(limit + 1)
        if len(raw) > limit:
            return default
        v = json.loads(raw.decode("utf-8-sig"))
        return v if isinstance(v, type(default)) else default
    except Exception:
        return default
    finally:
        if fd is not None:
            os.close(fd)


def sanitize_config(cfg):
    """Лише допустимі ключі й типи; усе інше ігнорується (захист від зіпсованого/ворожого конфігу)."""
    d = dict(DEFAULT_CONFIG)

    def num(k, lo, hi):
        v = cfg.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi:
            d[k] = float(v)

    num("min_gross_margin_pct", 0, 99.9)
    num("price_outlier_ratio", 2, 100000)
    for k in ("lint_block_on_error", "stop_check_enabled"):
        if isinstance(cfg.get(k), bool):
            d[k] = cfg[k]
    v = cfg.get("legal_as_of")
    if isinstance(v, str) and re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", v):
        d["legal_as_of"] = v
    t = cfg.get("confidential_terms")
    if isinstance(t, list):
        d["confidential_terms"] = [x.strip() for x in t if isinstance(x, str) and 3 <= len(x.strip()) <= 80][:200]
    return d


def load_config(project_dir=None):
    raw = {}
    raw.update(_load_json(os.path.join(DATA_DIR, "config.json"), {}))
    if project_dir:
        raw.update(_load_json(os.path.join(project_dir, ".claude", "furniture-expert.json"), {}))
    return sanitize_config(raw)


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read(MAX_BYTES)
    for cut in (0, 1, 2, 3):
        try:
            return (raw[:-cut] if cut else raw).decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
    t = raw.decode("utf-8", errors="replace")
    if t.count("\ufffd") <= max(3, len(t) // 100):
        return t
    return raw.decode("cp1251", errors="replace")


def _printable(s):
    """Керуючі й форматні символи (ESC, bidi, zero-width, розділювачі рядків) -> пробіл. Текст із файлу — чужі дані:
    він не повинен додавати рядків чи розмітки у відповідь хука, яку читає модель."""
    return "".join(" " if unicodedata.category(c)[0] == "C" or c in u"\u2028\u2029" else c for c in s)


def snip(s, n=60):
    s = re.sub(r"\s+", " ", _printable(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def line_snip(block, start, n=60):
    """Фрагмент від start до кінця рядка (не перетинає рядки), ≤ n символів."""
    return snip(block[start:start + 300].split("\n")[0], n)


def is_inside(path, folder):
    try:
        p = os.path.realpath(path)
        f = os.path.realpath(folder)
        return p == f or p.startswith(f + os.sep)
    except Exception:
        return False


# ------------------------------------------------------------------ preprocessing

_BLOCK_END = re.compile(r"</(?:p|tr|div|section|article|ul|ol|table|h[1-6]|description|offer|name)>", re.I)
_LINE_END = re.compile(r"<br\s{0,3}/?>|</li>|</td>|</th>", re.I)
_OPEN_SC = re.compile(r"<(script|style)\b", re.I)
_TAG = re.compile(r"<[^<>]{0,2000}>")


_LONG_CHARREF = re.compile(r"&#(?:[xX][0-9a-fA-F]{9,}|[0-9]{9,})")


def _unescape(t):
    """html.unescape, але без числових посилань довших за будь-який кодпоінт (&#99999…): на Python ≥ 3.11 вони
    кидають ValueError (ліміт int), на старіших — повільні. Таке посилання замінюється пробілом."""
    return _html.unescape(_LONG_CHARREF.sub(" ", t))


def _strip_comments(t):
    out, pos = [], 0
    while True:
        i = t.find("<!--", pos)
        if i < 0:
            out.append(t[pos:])
            break
        out.append(t[pos:i])
        j = t.find("-->", i + 4)
        if j < 0:
            break  # незакритий коментар — решта є коментарем
        pos = j + 3
    return " ".join(out)


def _strip_scripts(t):
    out, pos = [], 0
    while True:
        m = _OPEN_SC.search(t, pos)
        if not m:
            out.append(t[pos:])
            break
        out.append(t[pos:m.start()])
        c = re.compile(r"</%s\s{0,3}>" % m.group(1), re.I).search(t, m.end())
        if not c:
            break
        pos = c.end()
    return " ".join(out)


_CLOSE_CSSJS = {"script": re.compile(r"</script\s{0,3}>", re.I), "style": re.compile(r"</style\s{0,3}>", re.I)}
_STYLE_ATTR = re.compile(r"\sstyle\s{0,3}=\s{0,3}(?:\"[^\"\n]{0,2000}\"|'[^'\n]{0,2000}')", re.I)
_FENCE_CSS = re.compile(r"^\s{0,3}(```|~~~)[`~]*\s{0,3}(?:css|scss|less)\b", re.I)


def _strip_css_js(t):
    """Для перевірки витоків: прибирає ЗАКРИТІ блоки <style>/<script> і атрибути style="…" (CSS — не закупівельні дані).
    Незакритий тег нічого не ховає; коментарі та інші атрибути лишаються, бо витік у них теж публічний."""
    out, pos = [], 0
    while True:
        m = _OPEN_SC.search(t, pos)
        if not m:
            out.append(t[pos:])
            break
        c = _CLOSE_CSSJS[m.group(1).lower()].search(t, m.end())
        if not c:
            out.append(t[pos:])
            break
        out.append(t[pos:m.start()])
        pos = c.end()
    return _STYLE_ATTR.sub(" ", " ".join(out))


def _strip_css_fences(t):
    """Те саме для Markdown: закриті блоки ```css / ~~~scss. Незакритий блок вважається звичайним текстом."""
    lines = t.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        m = _FENCE_CSS.match(lines[i])
        if m:
            j = i + 1
            while j < n and not lines[j].lstrip().startswith(m.group(1)):
                j += 1
            if j < n:
                out.append("")
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def markup_to_text(raw):
    t = _strip_scripts(_strip_comments(raw))
    t = t.replace("<![CDATA[", "").replace("]]>", "")
    t = _BLOCK_END.sub("\n\n", t)
    t = _LINE_END.sub("\n", t)
    t = _TAG.sub(" ", t)
    t = _unescape(t)
    return _TAG.sub(" ", t)  # другий прохід: екрановані теги з CDATA


def _chunks(start, text):
    """Ріже надто довгі блоки по рядках/символах (≤ MAX_BLOCK)."""
    if len(text) <= MAX_BLOCK:
        yield start, text
        return
    cur, size, first, ln = [], 0, start, start
    for line in text.split("\n"):
        while len(line) > MAX_BLOCK:
            if cur:
                yield first, "\n".join(cur)
                cur, size = [], 0
            yield ln, line[:MAX_BLOCK]
            line = line[MAX_BLOCK:]
        if cur and size + len(line) + 1 > MAX_BLOCK:
            yield first, "\n".join(cur)
            cur, size, first = [], 0, ln
        if not cur:
            first = ln
        cur.append(line)
        size += len(line) + 1
        ln += 1
    if cur:
        yield first, "\n".join(cur)


def split_blocks(text, ext):
    """Повертає [(номер_рядка, текст_блоку)]. Блок = абзац / рядок таблиці / рядок CSV (≤ MAX_BLOCK)."""
    blocks = []
    cur = []
    start = 1
    per_line = ext in (".csv", ".tsv")
    for i, line in enumerate(text.split("\n"), 1):
        s_ = line.strip()
        if not s_:
            if cur:
                blocks.extend(_chunks(start, " \n".join(cur)))
                cur = []
            continue
        if per_line or s_.startswith("|") or s_.startswith("#"):
            if cur:
                blocks.extend(_chunks(start, " \n".join(cur)))
                cur = []
            blocks.extend(_chunks(i, s_))
            continue
        if not cur:
            start = i
        cur.append(s_)
    if cur:
        blocks.extend(_chunks(start, " \n".join(cur)))
    return blocks


# ----------------------------------------------------------------- dictionaries


def _token_re(tokens):
    """Один regex на список токенів: початок слова; пробіл = 1–3 пробіли; «$» у кінці — ціле слово. Довші — першими."""
    alts = []
    for tok in sorted(set(x.lower() for x in tokens if isinstance(x, str) and x.strip()), key=len, reverse=True):
        whole = tok.endswith("$")
        body = r"\s{1,3}".join(re.escape(part) for part in tok.rstrip("$").split())
        if body:
            alts.append(body + (r"(?!\w)" if whole else ""))
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + ")") if alts else None


def _sane_range(r):
    return (isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in r)
            and 0 < r[0] < r[1])


class Lexicon(object):
    def __init__(self):
        mj = _load_json(os.path.join(DATA_DIR, "materials.json"), {}, limit=2000000)
        mats = mj.get("materials") if isinstance(mj.get("materials"), dict) else {}
        claims = mj.get("claims") if isinstance(mj.get("claims"), dict) else {}

        def family(*names):
            toks = []
            for spec in mats.values():
                if isinstance(spec, dict) and spec.get("family") in names and isinstance(spec.get("tokens"), list):
                    toks.extend(spec["tokens"])
            return _token_re(toks)

        def plain(v):
            return _token_re(v) if isinstance(v, list) else None

        self.board_re = family("board")
        self.wood_re = family("solid_wood", "veneer", "plywood")
        self.fake_leather_re = family("artificial_leather")
        self.wood_claim_re = plain(claims.get("solid_wood"))
        self.leather_claim_re = plain(claims.get("genuine_leather"))
        self.combo_re = plain(mj.get("combination_markers"))
        sp = _load_json(os.path.join(DATA_DIR, "product_specs.json"), {}, limit=2000000)
        self.specs = sp
        # для кожного виду параметра: аліас -> матеріал/виріб і один regex на всі аліаси (довші — першими)
        self.kinds = {}
        for kind in ("density", "thickness", "mattress_height"):
            items = [it for it in (sp.get(kind) or {}).get("items", []) if _sane_range(it.get("range"))]
            amap = {}
            for it in items:
                for al in it.get("aliases", []):
                    if isinstance(al, str) and al.strip():
                        amap.setdefault(al.lower(), it)
            rx = None
            if amap:
                alts = "|".join(re.escape(a) for a in sorted(amap, key=len, reverse=True))
                rx = re.compile(r"(?<!\w)(" + alts + ")")
            self.kinds[kind] = (amap, rx)

    def plain_range(self, kind):
        r = (self.specs.get(kind) or {}).get("range")
        return r if _sane_range(r) else None

    def max_cm(self):
        v = (self.specs.get("dimensions") or {}).get("max_cm")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


# Вимірювані параметри меблів. Усі регулярні вирази працюють по рядку в нижньому регістрі; квантифікатори обмежені.
_NUM = r"(\d{1,4}(?:[.,]\d{1,2})?)"
DENS_RE = re.compile(
    r"(?<![\d.,])" + _NUM + r"\s{0,3}(?:кг\s{0,2}/\s{0,2}(?:м\s{0,2}[³3]|куб\.?\s{0,2}м)|kg\s{0,2}/\s{0,2}m\s{0,2}[³3])")
THICK_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s{0,2}(?:мм|mm)(?!\w)")
MART_KW_RE = re.compile(r"мартінд\w{0,8}|мартинд\w{0,8}|martindale")
MART_NUM_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[   .,]\d{3})+|\d{1,7})(?![\d])(?:\s{0,2}(тис|тыс|k)(?!\w)\.?)?")
SPRINGS_RE = re.compile(
    r"(?<![\d.,])(\d{2,4})\s{0,3}(?:(?:незалежн|независим|independent|niezależn)\w{0,4}\s{1,3})?"
    r"(?:пружин\w{0,4}|springs?|sprężyn\w{0,3}|sprezyn\w{0,3})\s{0,3}(?:/|на|per|na)\s{0,3}(?:1\s{0,2})?"
    r"(?:м\s{0,2}[²2]|кв\.?\s{0,2}м|m\s{0,2}[²2]|sq\.?\s{0,2}m)(?!\w)")
HEIGHT_RE = re.compile(
    r"(?:висот\w{0,6}|высот\w{0,6}|height|wysoko\w{0,4})[^\d\n]{0,15}?(\d{1,3}(?:[.,]\d)?)\s{0,2}(?:см|cm)(?!\w)")
_DIM = r"(\d{1,5}(?:[.,]\d{1,2})?)"
_X = r"\s{0,2}[×xх*]\s{0,2}"
DIMS_RE = re.compile(
    r"(?<![\d.,])" + _DIM + _X + _DIM + r"(?:" + _X + _DIM + r")?(?![\d.,])\s{0,3}(см|cm|мм|mm|м|m)?(?!\w)")
DIM_ONE_RE = re.compile(
    r"(?:ширин\w{0,4}|глибин\w{0,4}|глубин\w{0,4}|висот\w{0,4}|высот\w{0,4}|довжин\w{0,4}|длин\w{0,4}|"
    r"width|depth|height|length|szeroko\w{0,4}|głęboko\w{0,4}|wysoko\w{0,4}|długo\w{0,4})"
    r"[^\d\n]{0,15}?(\d{1,5}(?:[.,]\d{1,2})?)\s{0,2}(?:см|cm)(?!\w)")
UNIT_CM_RE = re.compile(r"(?<!\w)(?:см|cm)(?!\w)")
UNIT_MM_RE = re.compile(r"(?<!\w)(?:мм|mm)(?!\w)")
CLAUSE_SPLIT_RE = re.compile(r"[.;!?|\n]")

MED_RE = re.compile(
    r"гіпоалергенн\w{0,15}|гипоаллергенн\w{0,15}|антибактеріальн\w{0,15}|антибактериальн\w{0,15}|антимікробн\w{0,15}|"
    r"антиалергенн\w{0,15}|лікувальн\w{0,15}|лечебн\w{0,15}|ортопедичн\w{0,15}|терапевтичн\w{0,15}|"
    r"протикліщов\w{0,15}|антиклещев\w{0,15}", re.I)
CERT_RE = re.compile(
    r"oeko[-\s]?tex|\bgots\b|\bocs\b|\bbci\b|global\s{1,3}organic\s{1,3}textile|better\s{1,3}cotton", re.I)
ORIGIN_RE = re.compile(
    r"єгипетськ\w{0,8}\s{1,3}бавовн|египетск\w{0,8}\s{1,3}хлоп|egyptian\s{1,3}cotton|\bgiza\b|\bsupima\b|\bpima\b",
    re.I)

# Витік закупівельних даних. «Ключові слова вартості» ловимо лише поруч із числом (≤ 30 знаків), щоб стаття про
# облік собівартості без цифр не блокувалась. Усі квантифікатори обмежені (захист від ReDoS).
LEAK_KEYWORDS = [
    (re.compile(r"собівартіст\w{0,6}|себестоимост\w{0,6}", re.I), "собівартість"),
    (re.compile(
        r"закуп\w{0,12}\s{1,3}(?:ціна|ціни|ціну|цін\w{0,3}|вартіст\w{0,3}|цена|цены|цену)|"
        r"(?:ціна|цена|вартість|стоимость)\s{1,3}закуп\w{0,12}|закупочн\w{0,6}\s{1,3}цен\w{0,3}", re.I),
     "закупівельна ціна"),
    (re.compile(
        r"ціна\s{1,3}(?:від\s{1,3})?постачальник\w{0,6}|цена\s{1,3}поставщик\w{0,6}|supplier\s{1,3}price|"
        r"cost\s{1,3}price|landed\s{1,3}cost|purchase\s{1,3}price|wholesale\s{1,3}cost", re.I),
     "ціна постачальника / landed cost"),
    (re.compile(
        r"einkaufspreis\w{0,2}|ek[\s\-]{0,2}preis\w{0,2}|selbstkosten|"
        r"preço\s{1,3}de\s{1,3}(?:custo|compra)|custo\s{1,3}unitário", re.I),
     "закупівельна ціна (DE/PT)"),
    (re.compile(r"(?<!\w)(?:марж\w{0,3}|margin|націнк\w{0,3}|наценк\w{0,3}|markup)(?!\w)", re.I), "маржа/націнка"),
]
LEAK_DIRECT = [
    (re.compile(r"\b(?:FOB|EXW|CIF|CFR|DAP|DDP|FCA)\b[\s:\-$€]{0,10}\d", re.I), "ціна за Incoterms"),
    (re.compile(
        r"1688\.com|alibaba\.com|made-in-china\.com|aliexpress\.com|taobao\.com|tmall\.com|wlw\.de|europages\.|"
        r"(?<!\w)(?:wechat|weixin|вічат|вейчат)", re.I), "джерело/контакт постачальника"),
]
COST_COLS = {
    "cost", "cost price", "purchase price", "price purchase", "supplier price", "supplier", "margin",
    "собівартість", "себестоимость", "закупка", "закупівельна ціна", "закупочная цена", "постачальник",
    "поставщик", "маржа", "націнка", "наценка", "einkaufspreis", "ek preis", "ek", "preço de custo", "custo",
    "preço de compra",
}
ZW_RE = re.compile("[\u200b-\u200f\u2060\ufeff\u00ad\u202a-\u202e]")

RU_LETTERS_RE = re.compile(r"[ыэъё]", re.I)
RU_WORDS_RE = re.compile(
    r"постельн|бельё|белье|белья|полотенц|\bткань\b|\bткани\b|хлопок|хлопков|шелк|пододеяльник|наволочк|"
    r"простын|одеял|плотност|размер|\bцвет\b|\bцвета\b|стирк|\bсостав\b", re.I)


def _sev(sev, code, line, msg):
    return {"sev": sev, "code": code, "line": line, "msg": msg}


def check_block(lineno, block, lex, ctx, out):
    bl = block.lower()
    check_materials(lineno, bl, lex, out)
    check_specs(lineno, bl, lex, out)
    check_dimensions(lineno, bl, lex, out)

    # ---- заяви, що потребують доказів (одноразово на файл)
    for m in MED_RE.finditer(block):
        w = snip(m.group(0).lower(), 40)
        if ("med", w) not in ctx["seen"]:
            ctx["seen"].add(("med", w))
            out.append(_sev("WARN", "CLAIM_MED", lineno,
                            "заява «%s» потребує протоколу випробувань/сертифіката (інакше — недостовірна реклама)" % w))
    if CERT_RE.search(block) and ("cert",) not in ctx["seen"]:
        ctx["seen"].add(("cert",))
        out.append(_sev("WARN", "CLAIM_CERT", lineno,
                        "згадано сертифікат (OEKO-TEX/GOTS/OCS/BCI): вкажіть номер/клас і підтвердіть чинність саме для цього виробника та позиції"))
    if ORIGIN_RE.search(block) and ("origin",) not in ctx["seen"]:
        ctx["seen"].add(("origin",))
        out.append(_sev("WARN", "CLAIM_ORIGIN", lineno,
                        "«єгипетська/Giza/Pima/Supima» — потрібне документальне підтвердження походження сировини"))


def check_materials(lineno, bl, lex, out):
    """Заяви про матеріал, що суперечать матеріалу в тому ж реченні (частині тексту до . ; ! ? | або кінця рядка)."""
    done = set()
    pos = 0
    for clause in CLAUSE_SPLIT_RE.split(bl):
        start, pos = pos, pos + len(clause) + 1
        if "MAT_SOLID_WOOD" not in done and lex.board_re and lex.wood_claim_re:
            claim = lex.wood_claim_re.search(clause)
            board = claim and lex.board_re.search(clause)
            if board and not (lex.wood_re and lex.wood_re.search(clause)):
                done.add("MAT_SOLID_WOOD")
                out.append(_sev(
                    "ERROR", "MAT_SOLID_WOOD", lineno,
                    "«%s» поруч із плитою «%s» без породи деревини: «%s» — ДСП/МДФ/ДВП не є масивом; назвіть породу "
                    "для дерев'яних частин або приберіть заяву" % (claim.group(0), board.group(0), snip(clause, 60))))
        if "MAT_LEATHER" not in done and lex.fake_leather_re and lex.leather_claim_re:
            claim = lex.leather_claim_re.search(clause)
            fake = claim and lex.fake_leather_re.search(clause)
            if fake and not (lex.combo_re and lex.combo_re.search(clause)):
                done.add("MAT_LEATHER")
                out.append(_sev(
                    "ERROR", "MAT_LEATHER", lineno,
                    "«%s» в одному описі з «%s»: «%s» — уточніть, які частини з якого матеріалу (сидіння — шкіра, "
                    "боковини — екошкіра) або приберіть заяву" % (claim.group(0), fake.group(0), snip(clause, 60))))


def _num(s):
    return float(s.replace(",", "."))


def _line_bounds(bl, pos):
    ls = bl.rfind("\n", 0, pos) + 1
    le = bl.find("\n", pos)
    return ls, (len(bl) if le < 0 else le)


def _pick_near(bl, start, end, kind, lex):
    """Матеріал для числа bl[start:end]: найближча попередня назва в тому ж рядку (≤ 40 знаків, без цифр між ними),
    інакше назва одразу після числа з одиницею («16 мм ЛДСП»). Інакше None — без перевірки, щоб не давати хибних тривог."""
    amap, rx = lex.kinds.get(kind, ({}, None))
    if rx is None:
        return None
    ls, le = _line_bounds(bl, start)
    best = None
    for m in rx.finditer(bl, max(ls, start - 80), start):
        if start - m.end() <= 40 and not re.search(r"\d", bl[m.end():start]):
            best = m
    if best is not None:
        return amap.get(best.group(1))
    j = end
    while j < min(le, end + 4) and bl[j] in " \t(:,":
        j += 1
    m = rx.match(bl, j)
    if m and m.start() < le:
        return amap.get(m.group(1))
    return None


def _pick_in_line(bl, start, kind, lex):
    """Для висоти матраца: назва виробу в тому ж рядку (єдина або найближча попередня)."""
    amap, rx = lex.kinds.get(kind, ({}, None))
    if rx is None:
        return None
    ls, le = _line_bounds(bl, start)
    found = [(m.end(), amap.get(m.group(1))) for m in rx.finditer(bl, ls, le)]
    found = [f for f in found if f[1] is not None]
    if len(set(f[1]["key"] for f in found)) == 1:
        return found[0][1]
    prev = [f for f in found if f[0] <= start]
    return max(prev, key=lambda f: f[0])[1] if prev else None


def _g(v):
    """Число для повідомлення: 1 500 000 замість 1.5e+06."""
    return "{:,.0f}".format(v).replace(",", " ") if v == int(v) and abs(v) >= 10000 else "%g" % v


def _range_issue(lineno, v, lo, hi, what, unit, note, out):
    if lo * 0.95 <= v <= hi * 1.05:
        return
    hard = v < lo * 0.6 or v > hi * 1.8
    out.append(_sev(
        "ERROR" if hard else "WARN", "SPEC_RANGE", lineno,
        "%s %s %s нетипово (ринковий діапазон %s–%s)%s; перевірте одиниці/позицію"
        % (what, _g(v), unit, _g(lo), _g(hi), (" (" + note + ")") if note else "")))


def check_specs(lineno, bl, lex, out):
    """Вимірювані параметри проти діапазонів із data/product_specs.json."""
    for m in DENS_RE.finditer(bl):
        it = _pick_near(bl, m.start(), m.end(), "density", lex)
        if it is not None:
            _range_issue(lineno, _num(m.group(1)), it["range"][0], it["range"][1],
                         "щільність «%s»" % it.get("key", "?"), "кг/м³", it.get("note"), out)
    for m in THICK_RE.finditer(bl):
        if re.search(r"[×xх*]\s{0,2}$", bl[max(0, m.start() - 4):m.start()]) or re.match(r"\s{0,2}[×xх*]", bl[m.end():m.end() + 3]):
            continue  # частина габаритів «2000×900×750 мм»
        it = _pick_near(bl, m.start(), m.end(), "thickness", lex)
        if it is not None:
            _range_issue(lineno, _num(m.group(1)), it["range"][0], it["range"][1],
                         "товщина «%s»" % it.get("key", "?"), "мм", it.get("note"), out)
    mr = lex.plain_range("martindale")
    if mr:
        for kw in MART_KW_RE.finditer(bl):
            ls, le = _line_bounds(bl, kw.start())
            a, b = max(ls, kw.start() - 40), min(le, kw.end() + 40)
            nums = [n for n in MART_NUM_RE.finditer(bl, a, b) if n.end() <= kw.start() or n.start() >= kw.end()]
            if not nums:
                continue
            n = min(nums, key=lambda n: min(abs(n.end() - kw.start()), abs(n.start() - kw.end())))
            v = float(re.sub(r"[   .,]", "", n.group(1))) * (1000 if n.group(2) else 1)
            if v >= 1000:
                _range_issue(lineno, v, mr[0], mr[1], "стійкість до стирання (Мартіндейл)", "циклів",
                             (lex.specs.get("martindale") or {}).get("note"), out)
    sr = lex.plain_range("springs_per_m2")
    if sr:
        for m in SPRINGS_RE.finditer(bl):
            _range_issue(lineno, float(m.group(1)), sr[0], sr[1], "кількість пружин", "на м²",
                         (lex.specs.get("springs_per_m2") or {}).get("note"), out)
    for m in HEIGHT_RE.finditer(bl):
        it = _pick_in_line(bl, m.start(), "mattress_height", lex)
        if it is not None:
            _range_issue(lineno, _num(m.group(1)), it["range"][0], it["range"][1],
                         "висота «%s»" % it.get("key", "?"), "см", it.get("note"), out)


def check_dimensions(lineno, bl, lex, out):
    """Габарити в см, що фізично неможливі для меблів, — майже завжди міліметри з підписом «см»."""
    limit = lex.max_cm()
    if not limit:
        return
    hits = []
    for m in DIMS_RE.finditer(bl):
        unit = m.group(4)
        if not unit:
            ls, _ = _line_bounds(bl, m.start())
            before = bl[max(ls, m.start() - 40):m.start()]
            cm, mm = list(UNIT_CM_RE.finditer(before)), list(UNIT_MM_RE.finditer(before))
            if cm and (not mm or cm[-1].start() > mm[-1].start()):
                unit = "см"
        if unit in ("см", "cm"):
            vals = [_num(g) for g in m.groups()[:3] if g]
            if max(vals) > limit:
                hits.append(m)
    for m in DIM_ONE_RE.finditer(bl):
        if _num(m.group(1)) > limit:
            hits.append(m)
    if hits:
        m = hits[0]
        out.append(_sev("ERROR", "DIM_UNIT", lineno,
                        "габарит понад %g см: «%s» — схоже на міліметри; вкажіть розміри в см (Ш×Г×В) або змініть одиницю"
                        % (limit, snip(bl[m.start():m.end()], 40))))


def _keyword_near_number(rx, text, limit=50):
    """Ключове слово вартості, поруч (≤ 30 знаків у тому ж рядку) з цифрою."""
    for i, m in enumerate(rx.finditer(text)):
        if i >= limit:
            break
        before = text[max(0, m.start() - 30):m.start()].split("\n")[-1]
        after = text[m.end():m.end() + 30].split("\n")[0]
        if re.search(r"\d", before) or re.search(r"\d", after):
            return m
    return None


def _norm_for_scan(raw):
    t = unicodedata.normalize("NFKC", _unescape(raw))
    return ZW_RE.sub("", t)


def check_leaks(raw_ok, ext, cfg, out):
    norm = _norm_for_scan(raw_ok)
    texts = [norm]
    if "<" in norm:
        texts.append(_TAG.sub("", norm))  # «соб<b></b>івартість»
    found = set()
    for t in texts:
        for rx, name in LEAK_KEYWORDS:
            if name in found:
                continue
            m = _keyword_near_number(rx, t)
            if m:
                found.add(name)
                out.append(_sev("ERROR", "LEAK", 0, "у публічному тексті дані закупівлі (%s): «%s» — приберіть, "
                                "позначте рядок furniture-expert:ok або файл furniture-expert:internal"
                                % (name, snip(t[max(0, m.start() - 10):m.end() + 20], 40))))
        for rx, name in LEAK_DIRECT:
            if name in found:
                continue
            m = rx.search(t)
            if m:
                found.add(name)
                out.append(_sev("ERROR", "LEAK", 0, "у публічному тексті: %s: «%s» — приберіть, "
                                "позначте рядок furniture-expert:ok або файл furniture-expert:internal"
                                % (name, snip(t[max(0, m.start() - 10):m.end() + 20], 40))))
    low = norm.lower()
    for term in cfg.get("confidential_terms", []) or []:
        if isinstance(term, str) and term.strip() and term.strip().lower() in low:
            out.append(_sev("ERROR", "LEAK_TERM", 0,
                            "знайдено конфіденційний термін із config (confidential_terms) — публічний текст не повинен його містити"))
            break
    if ext in (".csv", ".tsv"):
        first = next((ln for ln in raw_ok.split("\n", 50)[:50] if ln.strip()), "").lstrip("\ufeff")
        delim = max((";", ",", "\t"), key=lambda d: first.count(d))
        cols = [re.sub(r"[\s_\-]+", " ", c.strip().strip("\"'").lower()) for c in first.split(delim)]
        bad = [c for c in cols if c in COST_COLS]
        if bad:
            out.append(_sev("ERROR", "LEAK_COL", 1,
                            "у публічному фіді колонка закупівельних даних «%s» — приберіть колонку або позначте файл furniture-expert:internal"
                            % snip(bad[0], 30)))


def check_public_text(raw_ok, text, ext, cfg, out):
    """Перевірки, що мають сенс лише для публічного тексту."""
    check_leaks(raw_ok, ext, cfg, out)
    if re.search(r'lang\s{0,3}[=:]\s{0,3}["\']?ru|furniture-expert:lang=ru', raw_ok[:4000], re.I):
        return
    plain = re.sub(r"https?://\S{1,300}", " ", text)
    n = len(RU_LETTERS_RE.findall(plain)) + len(RU_WORDS_RE.findall(plain))
    if n >= 3:
        out.append(_sev("WARN", "LANG_RU", 0,
                        "схоже на російську лексику/літери (ы, э, ъ, ё, «ткань», «размер»…) — ринок України: контент українською (≈%d збігів)" % n))


def lint_text(raw, ext, cfg, public=True):
    lex = Lexicon()
    text = markup_to_text(raw) if ext in MARKUP_EXT else raw
    raw_ok = "\n".join("" if "furniture-expert:ok" in ln else ln for ln in raw.split("\n"))
    text = "\n".join("" if "furniture-expert:ok" in ln else ln for ln in text.split("\n"))
    out = []
    ctx = {"seen": set()}
    deadline = time.monotonic() + TIME_BUDGET_S
    for lineno, block in split_blocks(text, ext):
        if len(out) >= MAX_ISSUES:
            break
        if time.monotonic() > deadline:
            out.append(_sev("WARN", "PARTIAL", lineno,
                            "файл завеликий — перевірено лише початок (до рядка %d); решту перевірте вручну/частинами" % lineno))
            break
        try:
            check_block(lineno, block, lex, ctx, out)
        except Exception:
            if os.environ.get("FURNITURE_EXPERT_DEBUG"):
                traceback.print_exc()
    if public:
        try:
            leak_src = _strip_css_js(raw_ok) if ext in MARKUP_EXT else _strip_css_fences(raw_ok)
            check_public_text(leak_src, text, ext, cfg, out)
        except Exception:
            if os.environ.get("FURNITURE_EXPERT_DEBUG"):
                traceback.print_exc()
            out.append(_sev("WARN", "SCAN_FAILED", 0,
                            "перевірку витоків закупівельних даних не виконано (внутрішня помилка) — перевірте файл вручну"))
    return out


def _tokens(name):
    return set(t for t in re.split(r"[^0-9a-zа-яіїєґ]+", name.lower()) if t)


def classify(path, raw):
    """Повертає (lintable, public)."""
    ext = os.path.splitext(path)[1].lower()
    base = os.path.basename(path)[:80].lower()
    if ext not in LINT_EXT or base in SKIP_NAMES:
        return False, False
    if is_inside(path, SKILL_DIR):
        return False, False
    parts = os.path.realpath(path).split(os.sep)
    for i, p in enumerate(parts):
        if p in (".git", "node_modules"):
            return False, False
        if p == ".claude" and i + 1 < len(parts) and parts[i + 1] in SKIP_CLAUDE_SUBDIRS:
            return False, False
    if "furniture-expert:internal" in raw[:4000]:
        return True, False
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if (_tokens(os.path.splitext(base)[0]) | _tokens(parent)) & INTERNAL_TOKENS:
        return True, False
    return True, True


def lint_file(path, cfg, force_public=None):
    raw = read_text(path)
    ext = os.path.splitext(path)[1].lower()
    lintable, public = classify(path, raw)
    if force_public is not None:
        lintable, public = True, force_public
    if not lintable:
        return []
    return lint_text(raw, ext, cfg, public)


# ----------------------------------------------------------------------- output


def _fmt(issues, limit=10):
    lines = []
    for i in issues[:limit]:
        where = ("рядок %d: " % i["line"]) if i["line"] else ""
        lines.append("• [%s] %s%s" % (i["code"], where, i["msg"]))
    if len(issues) > limit:
        lines.append("• …і ще %d" % (len(issues) - limit))
    return "\n".join(lines)


def hook_main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")  # завжди UTF-8, а не локаль процесу
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path")
    if not fp or not isinstance(fp, str):
        return 0
    cwd = data.get("cwd") or os.getcwd()
    path = fp if os.path.isabs(fp) else os.path.join(cwd, fp)
    if not os.path.isfile(path):
        return 0
    cfg = load_config(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    issues = lint_file(path, cfg)
    if not issues:
        return 0
    errs = [i for i in issues if i["sev"] == "ERROR"]
    warns = [i for i in issues if i["sev"] == "WARN"]
    out = {}
    if errs and cfg.get("lint_block_on_error", True):
        out["decision"] = "block"
        out["reason"] = (
            "furniture-expert: у файлі «%s» знайдено помилки, які треба виправити (або, якщо це свідоме рішення, позначити "
            "рядок furniture-expert:ok / файл furniture-expert:internal):\n%s" % (snip(os.path.basename(path), 80), _fmt(errs)))
        if warns:
            out["hookSpecificOutput"] = {
                "hookEventName": "PostToolUse",
                "additionalContext": "Попередження furniture-expert:\n" + _fmt(warns)}
    else:
        body = _fmt(errs + warns)
        out["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": "furniture-expert lint («%s»):\n%s" % (snip(os.path.basename(path), 80), body)}
    sys.stdout.write(json.dumps(out))
    return 0


def cli_main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="furniture-expert: перевірка тексту/фіду без хуків")
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--public", action="store_true", help="примусово як публічний текст")
    g.add_argument("--internal", action="store_true", help="примусово як внутрішній документ")
    a = ap.parse_args(argv)
    cfg = load_config(os.getcwd())
    force = True if a.public else (False if a.internal else None)
    issues = lint_file(a.file, cfg, force)
    if a.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    elif not issues:
        print("OK: зауважень немає")
    else:
        for i in issues:
            where = (" рядок %d" % i["line"]) if i["line"] else ""
            print("%s [%s]%s: %s" % (i["sev"], i["code"], where, i["msg"]))
    return 1 if any(i["sev"] == "ERROR" for i in issues) else 0


def main():
    if len(sys.argv) > 1:
        return cli_main(sys.argv[1:])
    try:
        return hook_main()
    except Exception:
        if os.environ.get("FURNITURE_EXPERT_DEBUG"):
            traceback.print_exc()
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main())
