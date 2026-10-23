#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
furniture-expert / scripts/landed_cost.py — собівартість одиниці меблів і ціна продажу.

Локально, офлайн, лише stdlib. Нічого не пише на диск і не логує.
Результат — оцінка за вашими вхідними; ставки мита/ПДВ/курс беріть у брокера/бухгалтера на дату ввезення.

Режим import (контейнер із Китаю, машина з Польщі):
  python3 -I landed_cost.py --mode import --goods 42 --qty 360 --currency USD --fx 41.5 \
      --unit-cbm 0.18 --freight-per-cbm 95 --duty-pct 10 --broker-uah 12000 --inland-uah 18000 \
      --qc-uah 4000 --damage-pct 3 --margin-pct 35

Формули (import):
  доставка до кордону  = --freight (усього) або --unit-cbm × qty × --freight-per-cbm (у валюті)
  митна вартість       = (товар × qty + доставка до кордону) × курс
  мито                 = митна вартість × ставка (ставку підтверджує брокер; 0 % для товару з ЄС —
                         лише з доказом походження: EUR.1 або декларація на інвойсі)
  ПДВ на ввезенні      = (митна вартість + мито) × 20 %  (витрата, якщо ви НЕ платник ПДВ)
  собівартість партії  = митна вартість + мито + (ПДВ, якщо не платник) + брокер + доставка до складу
                         + банк/конвертація + контроль якості + пакування (грн/од. × qty)
  продається           = qty × (1 − пошкодження %)       (пошкодження в дорозі, брак, некомплект)
  собівартість 1 од.   = собівартість партії / продається

Ціна (обидва режими):
  ціна без ПДВ         = собівартість 1 од. / (1 − маржа %)       (маржа — від виручки без ПДВ)
  ціна для покупця     = ціна без ПДВ × (1 + ПДВ), якщо ви платник ПДВ
"""
from __future__ import print_function

import argparse
import json
import math
import sys


def yes(v):
    return str(v).strip().lower() in ("y", "yes", "так", "true", "1", "да")


def num(lo=None, hi=None):
    """argparse-тип: скінченне число в межах [lo, hi]."""
    def conv(s):
        try:
            v = float(s)
        except ValueError:
            raise argparse.ArgumentTypeError("не число: %r" % s)
        if not math.isfinite(v):
            raise argparse.ArgumentTypeError("значення має бути скінченним числом: %r" % s)
        if lo is not None and v < lo:
            raise argparse.ArgumentTypeError("значення %g менше допустимого %g" % (v, lo))
        if hi is not None and v > hi:
            raise argparse.ArgumentTypeError("значення %g більше допустимого %g" % (v, hi))
        return v
    return conv


def yn(s):
    v = str(s).strip().lower()
    if v in ("y", "yes", "так", "true", "1", "да"):
        return "yes"
    if v in ("n", "no", "ні", "false", "0", "нет"):
        return "no"
    raise argparse.ArgumentTypeError("очікується yes або no, отримано %r" % s)


# ---------------------------------------------------------------- собівартість

def compute_import(a):
    goods_cur = a.goods * a.qty
    volume = a.unit_cbm * a.qty if a.unit_cbm is not None else None
    freight_cur = volume * a.freight_per_cbm if a.freight_per_cbm is not None else a.freight
    customs_cur = goods_cur + freight_cur
    customs_uah = customs_cur * a.fx
    duty = customs_uah * a.duty_pct / 100.0
    import_vat = (customs_uah + duty) * a.vat_pct / 100.0
    bank = goods_cur * a.fx * a.bank_pct / 100.0
    vat_payer = yes(a.vat_payer)
    vat_cost = 0.0 if vat_payer else import_vat
    packaging = a.packaging_uah * a.qty
    total = customs_uah + duty + vat_cost + a.broker_uah + a.inland_uah + bank + a.qc_uah + packaging
    sellable = a.qty * (1 - a.damage_pct / 100.0)
    return {
        "mode": "import",
        "goods_total_cur": goods_cur,
        "volume_m3": volume,
        "freight_cur": freight_cur,
        "customs_value_uah": customs_uah,
        "duty_uah": duty,
        "import_vat_uah": import_vat,
        "import_vat_in_cost": not vat_payer,
        "bank_fee_uah": bank,
        "broker_uah": a.broker_uah,
        "inland_uah": a.inland_uah,
        "qc_uah": a.qc_uah,
        "packaging_uah": packaging,
        "total_cost_uah": total,
        "sellable_qty": sellable,
        "unit_cost_uah": total / sellable,
    }


# ---------------------------------------------------------------- ціна

def net_of(retail, a):
    return retail / (1 + a.vat_pct / 100.0) if yes(a.vat_payer) else retail


def retail_of(net, a):
    return net * (1 + a.vat_pct / 100.0) if yes(a.vat_payer) else net


def margin_at(retail, unit_cost, a):
    net = net_of(retail, a)
    return (net - unit_cost) / net * 100.0 if net else None


def compute_price(a, r):
    unit_cost = r["unit_cost_uah"]
    if a.margin_pct is not None:
        net = unit_cost / (1 - a.margin_pct / 100.0)
        r["target_margin_pct"] = a.margin_pct
        r["price_net_uah"] = net
        r["markup_pct"] = (net / unit_cost - 1) * 100.0 if unit_cost else None
        r["price_retail_uah"] = retail_of(net, a)
    if a.retail_price is not None:
        r["given_retail_price_uah"] = a.retail_price
        r["given_net_price_uah"] = net_of(a.retail_price, a)
        r["achieved_margin_pct"] = margin_at(a.retail_price, unit_cost, a)
    if a.rrp is not None:
        r["rrp_uah"] = a.rrp
        r["margin_at_rrp_pct"] = margin_at(a.rrp, unit_cost, a)
        if "price_retail_uah" in r:
            r["rrp_gap_uah"] = r["price_retail_uah"] - a.rrp
    for k in (5, 10):
        worse = unit_cost * (1 + k / 100.0)
        r["worse_%d_unit_cost_uah" % k] = worse
        if a.margin_pct is not None:
            r["worse_%d_price_retail_uah" % k] = retail_of(worse / (1 - a.margin_pct / 100.0), a)
        if a.retail_price is not None:
            r["worse_%d_achieved_margin_pct" % k] = margin_at(a.retail_price, worse, a)
    return r


# ---------------------------------------------------------------- звіт

def report_import(a, r):
    cur = a.currency
    if a.freight_per_cbm is not None:
        freight = "%.3f м³ × %g %s/м³ = %.2f %s" % (r["volume_m3"], a.freight_per_cbm, cur, r["freight_cur"], cur)
    else:
        freight = "%.2f %s усього" % (r["freight_cur"], cur)
        if r["volume_m3"] is not None:
            freight += " (обсяг партії %.3f м³)" % r["volume_m3"]
    return [
        "Вхідні: товар %g %s × %g = %.2f %s; доставка до кордону %s; курс %g; мито %g %%; ПДВ %g %%; платник ПДВ: %s"
        % (a.goods, cur, a.qty, r["goods_total_cur"], cur, freight, a.fx, a.duty_pct, a.vat_pct,
           "так" if yes(a.vat_payer) else "ні"),
        "Пошкодження/брак: %g %%; банк/конвертація: %g %%; пакування %g грн/од." % (a.damage_pct, a.bank_pct, a.packaging_uah),
        "",
        "Митна вартість:        %12.2f грн" % r["customs_value_uah"],
        "Мито:                  %12.2f грн" % r["duty_uah"],
        "ПДВ на ввезенні:       %12.2f грн  (%s)" % (
            r["import_vat_uah"], "витрата" if r["import_vat_in_cost"] else "податковий кредит, не в собівартості"),
        "Брокер:                %12.2f грн" % r["broker_uah"],
        "Доставка до складу:    %12.2f грн" % r["inland_uah"],
        "Банк/конвертація:      %12.2f грн" % r["bank_fee_uah"],
        "Контроль якості:       %12.2f грн" % r["qc_uah"],
        "Пакування:             %12.2f грн" % r["packaging_uah"],
        "-" * 44,
        "Повна собівартість:    %12.2f грн" % r["total_cost_uah"],
        "Придатно до продажу:   %12.2f од." % r["sellable_qty"],
        "Собівартість 1 од.:    %12.2f грн" % r["unit_cost_uah"],
    ]


def report_price(a, r):
    lines = []
    if "price_net_uah" in r:
        lines += [
            "",
            "Цільова маржа %g %% від виручки → ціна без ПДВ: %.2f грн (націнка %.1f %%)" % (
                r["target_margin_pct"], r["price_net_uah"], r["markup_pct"]),
            "Ціна для покупця: %.2f грн" % r["price_retail_uah"],
        ]
    if r.get("achieved_margin_pct") is not None:
        lines += ["", "При ціні %.2f грн (без ПДВ %.2f) валова маржа: %.1f %%" % (
            r["given_retail_price_uah"], r["given_net_price_uah"], r["achieved_margin_pct"])]
    if "rrp_uah" in r:
        lines += ["", "RRP/МРЦ %.2f грн: валова маржа при RRP %.1f %%" % (r["rrp_uah"], r["margin_at_rrp_pct"])]
        if "rrp_gap_uah" in r:
            gap = r["rrp_gap_uah"]
            lines.append("Розрахункова ціна %s RRP на %.2f грн%s" % (
                "вища за" if gap > 0 else "нижча за" if gap < 0 else "дорівнює",
                abs(gap), "" if gap <= 0 else " — продаж за RRP дасть меншу маржу за цільову"))
    worse = ["Сценарій «гірше»: собівартість +5 %% → %.2f грн, +10 %% → %.2f грн" % (
        r["worse_5_unit_cost_uah"], r["worse_10_unit_cost_uah"])]
    if "worse_5_price_retail_uah" in r:
        worse.append("ціна при цільовій маржі %.2f / %.2f грн" % (r["worse_5_price_retail_uah"], r["worse_10_price_retail_uah"]))
    if "worse_5_achieved_margin_pct" in r:
        worse.append("маржа при ціні %.2f грн: %.1f %% / %.1f %%" % (
            a.retail_price, r["worse_5_achieved_margin_pct"], r["worse_10_achieved_margin_pct"]))
    lines += ["", "; ".join(worse)]
    lines += ["", "Це оцінка за вашими вхідними, не митна чи податкова консультація: ставки, курс НБУ і режим ПДВ "
                  "підтвердіть у брокера/бухгалтера."]
    return lines


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="Собівартість одиниці меблів і ціна: імпорт або закупівля в Україні")
    ap.add_argument("--mode", choices=("import", "local"), required=True,
                    help="import — ввезення партії (Китай, Польща); local — закупівля в українського виробника")
    g = ap.add_argument_group("import")
    g.add_argument("--goods", type=num(0, 1e9), help="ціна товару за одиницю у валюті закупівлі")
    g.add_argument("--qty", type=num(0, 1e12), help="кількість одиниць у партії")
    g.add_argument("--currency", default="USD", help="валюта закупівлі (мітка): USD, EUR, PLN…")
    g.add_argument("--fx", type=num(0, 1e6), help="курс грн за 1 одиницю валюти (митний — курс НБУ на дату декларації)")
    g.add_argument("--freight", type=num(0, 1e12), default=None,
                   help="доставка+страхування до кордону України, у валюті, усього за партію")
    g.add_argument("--unit-cbm", type=num(0, 1000), default=None, help="обсяг однієї одиниці в упаковці, м³")
    g.add_argument("--freight-per-cbm", type=num(0, 1e9), default=None,
                   help="тариф доставки до кордону за 1 м³, у валюті (замість --freight; потребує --unit-cbm)")
    g.add_argument("--duty-pct", type=num(0, 500), default=None,
                   help="ставка мита, %% (обов'язково; беріть у брокера; 0 для ЄС лише з доказом походження)")
    g.add_argument("--broker-uah", type=num(0, 1e12), default=0.0)
    g.add_argument("--inland-uah", type=num(0, 1e12), default=0.0, help="доставка від кордону/порту до складу, усього")
    g.add_argument("--bank-pct", type=num(0, 100), default=1.0, help="комісії банку та конвертації, %% від суми платежу")
    g.add_argument("--qc-uah", type=num(0, 1e12), default=0.0, help="інспекція перед відвантаженням, усього")
    g.add_argument("--packaging-uah", type=num(0, 1e9), default=0.0, help="додаткове пакування/перепакування, грн за одиницю")
    c = ap.add_argument_group("спільні")
    c.add_argument("--vat-pct", type=num(0, 100), default=20.0)
    c.add_argument("--vat-payer", type=yn, default="no", help="чи ви платник ПДВ: yes/no")
    c.add_argument("--damage-pct", type=num(0, 99.99), default=3.0,
                   help="пошкодження в дорозі, брак, некомплект: %% одиниць, які не вдасться продати")
    c.add_argument("--margin-pct", type=num(0, 99.99), default=None, help="цільова валова маржа від виручки без ПДВ, %%")
    c.add_argument("--retail-price", type=num(0, 1e12), default=None, help="перевірити маржу при заданій ціні для покупця, грн")
    c.add_argument("--rrp", type=num(0, 1e12), default=None, help="рекомендована роздрібна ціна виробника (RRP/МРЦ), грн")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.retail_price is not None and a.retail_price <= 0:
        ap.error("retail-price має бути > 0")
    if a.rrp is not None and a.rrp <= 0:
        ap.error("rrp має бути > 0")
    if a.mode == "import":
        missing = [f for f, v in (("--goods", a.goods), ("--qty", a.qty), ("--fx", a.fx), ("--duty-pct", a.duty_pct))
                   if v is None]
        if missing:
            ap.error("для --mode import потрібні: " + ", ".join(missing))
        if a.qty <= 0 or a.fx <= 0:
            ap.error("qty і fx мають бути > 0")
        if a.freight is not None and a.freight_per_cbm is not None:
            ap.error("вкажіть або --freight (усього), або --freight-per-cbm (за м³), але не обидва")
        if a.freight_per_cbm is not None and a.unit_cbm is None:
            ap.error("--freight-per-cbm потребує --unit-cbm")
        if a.freight is None and a.freight_per_cbm is None:
            a.freight = 0.0
        r = compute_import(a)
        lines = report_import(a, r)
    else:
        ap.error("режим local ще не реалізовано")
    r = compute_price(a, r)
    print(json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False) if a.json else "\n".join(lines + report_price(a, r)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
