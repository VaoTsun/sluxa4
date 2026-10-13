# -*- coding: utf-8 -*-
"""
Ежедневная проверка цен на роботы-газонокосилки в Литве.

Типы источников (targets.json):
  - "jsonld"             -> страница товара со schema.org Product (JSON-LD)
  - "opencart_category"  -> страница категории OpenCart (несколько товаров)
  - "kainos_search"      -> поиск на агрегаторе kainos.lt (JSON-LD ItemList);
                            сразу отдаёт предложения разных магазинов

Результат:
  - reports\\report_ГГГГ-ММ-ДД_ЧЧММ.txt  (человекочитаемый отчёт)
  - reports\\latest.txt                    (последний отчёт)
  - state.json                             (цены прошлого запуска — для сравнения)
  - history.csv                            (история цен)
Скрипт печатает отчёт в stdout (его сохранит планировщик в лог).
"""
import csv
import datetime as dt
import html
import json
import os
import re
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
TARGETS = os.path.join(BASE, "targets.json")
STATE = os.path.join(BASE, "state.json")
HISTORY = os.path.join(BASE, "history.csv")
REPORTS = os.path.join(BASE, "reports")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "lt,ru;q=0.9,en;q=0.8",
}


# ---------------------------------------------------------------- helpers

def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_price(s):
    """'1 899.00€' -> 1899.0 ; '2299 €' -> 2299.0 ; '1 999,00 €' -> 1999.0"""
    if s is None:
        return None
    s = str(s).replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace("€", "").replace("EUR", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def money(v):
    if v is None:
        return "—"
    if abs(v - round(v)) < 0.005:
        return f"{round(v):,}".replace(",", " ") + " €"
    return f"{v:,.2f}".replace(",", " ") + " €"


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def jsonld_nodes(page: str):
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        yield from _walk(data)


def avail_text(avail: str) -> str:
    avail = avail or ""
    if "InStock" in avail or "instock" in avail.lower():
        return "в наличии"
    if "OutOfStock" in avail:
        return "нет в наличии"
    if "PreOrder" in avail or "BackOrder" in avail:
        return "под заказ"
    return ""


def _first_offer(node):
    offers = node.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers


# ---------------------------------------------------------------- parsers

def parse_jsonld(url: str):
    page = fetch(url)
    items = []
    for node in jsonld_nodes(page):
        if node.get("@type") != "Product" and not (
            isinstance(node.get("@type"), list) and "Product" in node["@type"]
        ):
            continue
        offers = _first_offer(node)
        price = offers.get("price")
        if price is None and isinstance(offers.get("priceSpecification"), dict):
            price = offers["priceSpecification"].get("price")
        items.append({
            "name": node.get("name", "").strip(),
            "price": parse_price(price),
            "old_price": None,
            "availability": avail_text(offers.get("availability", "")),
            "url": node.get("url") or offers.get("url") or url,
            "sku": str(node.get("sku", "") or ""),
        })
    return items


def parse_opencart_category(url: str, name_filter=None):
    page = fetch(url)
    items = []
    for block in re.split(r'<div class="product-layout', page)[1:]:
        nm = re.search(
            r'<div class="name">\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.S
        )
        if not nm:
            continue
        link = nm.group(1).strip()
        name = clean(nm.group(2))
        if name_filter and not re.search(name_filter, name, re.I):
            continue
        new = re.search(r'<span class="price-new">(.*?)</span>', block, re.S)
        old = re.search(r'<span class="price-old">(.*?)</span>', block, re.S)
        only = re.search(r'<div class="price">(.*?)</div>', block, re.S)
        if new:
            price = parse_price(clean(new.group(1)))
            old_price = parse_price(clean(old.group(1))) if old else None
        elif only:
            price = parse_price(clean(only.group(1)))
            old_price = None
        else:
            price, old_price = None, None
        items.append({
            "name": name,
            "price": price,
            "old_price": old_price,
            "availability": "",
            "url": link,
            "sku": "",
        })
    return items


def parse_kainos_search(url: str, exclude_sellers=None):
    """Агрегатор kainos.lt: JSON-LD ItemList, у каждого товара — лучшая цена и продавец."""
    exclude = {s.strip().lower() for s in (exclude_sellers or [])}
    page = fetch(url)
    items = []
    for node in jsonld_nodes(page):
        if node.get("@type") != "ItemList":
            continue
        for li in node.get("itemListElement", []):
            it = li.get("item", li)
            offers = _first_offer(it)
            seller = offers.get("seller")
            if isinstance(seller, dict):
                seller = seller.get("name")
            seller = (seller or "Kainos.lt").strip()
            if seller.lower() in exclude:
                continue
            items.append({
                "site": seller,                       # группируем по магазину-продавцу
                "name": it.get("name", "").strip(),
                "price": parse_price(offers.get("price")),
                "old_price": None,
                "availability": avail_text(offers.get("availability", "")),
                "url": it.get("url") or offers.get("url") or url,
                "sku": "",
            })
    return items


def parse_skelbiu_search(url: str, name_filter=None):
    """Доска объявлений skelbiu.lt: карточки <a ... standard-list-item> с .title и .price."""
    page = fetch(url)
    items = []
    starts = list(re.finditer(
        r'<a\s+href="([^"]+)"[^>]*class="[^"]*standard-list-item[^>]*>', page
    ))
    for idx, m in enumerate(starts):
        href = m.group(1)
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(page)
        block = page[m.end():end]
        title = re.search(r'<div class="title">(.*?)</div>', block, re.S)
        if not title:
            continue
        name = clean(title.group(1))
        if name_filter and not re.search(name_filter, name, re.I):
            continue
        price = re.search(
            r'<div class="price-item">\s*<div class="price">(.*?)</div>', block, re.S
        )
        loc = re.search(r'<div class="second-line">(.*?)</div>', block, re.S)
        link = href if href.startswith("http") else "https://www.skelbiu.lt" + href
        items.append({
            "name": name,
            "price": parse_price(clean(price.group(1))) if price else None,
            "old_price": None,
            "availability": clean(loc.group(1)) if loc else "",
            "url": link,
            "keyid": link,
            "sku": "",
        })
    return items


# ---------------------------------------------------------------- main

def key_of(site, name):
    return f"{site}|{name}"


def load_state():
    if os.path.exists(STATE):
        try:
            with open(STATE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    with open(TARGETS, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    now = dt.datetime.now()
    prev = load_state()
    current = {}
    rows = []
    seen = set()
    errors = []

    for t in cfg["targets"]:
        site = t["site"]
        label = t.get("label", "")
        try:
            if t["type"] == "jsonld":
                items = parse_jsonld(t["url"])
            elif t["type"] == "opencart_category":
                items = parse_opencart_category(t["url"], t.get("filter"))
            elif t["type"] == "kainos_search":
                items = parse_kainos_search(t["url"], t.get("exclude_sellers"))
            elif t["type"] == "skelbiu_search":
                items = parse_skelbiu_search(t["url"], t.get("filter"))
            else:
                items = []
            if not items:
                errors.append(f"{site} / {label}: товары не найдены")
            for it in items:
                s = it.get("site") or site           # агрегатор возвращает магазин-продавец
                k = key_of(s, it.get("keyid") or it["name"])
                if k in seen:
                    continue
                seen.add(k)
                old = prev.get(k, {})
                change = None
                if old.get("price") is not None and it["price"] is not None:
                    d = it["price"] - old["price"]
                    if abs(d) >= 0.005:
                        change = d
                it["site"] = s
                current[k] = {
                    "site": s, "label": label, "name": it["name"],
                    "price": it["price"], "availability": it["availability"],
                    "url": it["url"], "sku": it["sku"],
                    "checked": now.strftime("%Y-%m-%d %H:%M"),
                }
                rows.append((s, label, it, change, old))
        except Exception as e:
            errors.append(f"{site} / {label}: {type(e).__name__}: {e}")

    # ---- report
    L = []
    L.append("=" * 64)
    L.append(f"ПРОВЕРКА ЦЕН — {now.strftime('%Y-%m-%d %H:%M')}")
    L.append(f"Тема: {cfg.get('title', '')}")
    L.append("=" * 64)

    last_site = None
    for s, label, it, change, old in rows:
        if s != last_site:
            L.append("")
            L.append(f"### {s}")
            last_site = s
        L.append("")
        if label:
            L.append(f"[{label}]")
        L.append(f"  {it['name']}")
        line = f"  Цена: {money(it['price'])}"
        if it.get("old_price"):
            line += f"  (до скидки: {money(it['old_price'])})"
        if it.get("availability"):
            line += f"  [{it['availability']}]"
        L.append(line)
        if change is not None:
            arrow = "↓" if change < 0 else "↑"
            L.append(f"  ИЗМЕНЕНИЕ: {arrow} {money(abs(change))} с прошлого запуска")
        elif old.get("price") is not None:
            L.append("  изменение: без изменений")
        else:
            L.append("  изменение: первая проверка")
        L.append(f"  {it['url']}")

    maxp = cfg.get("max_price")
    if maxp:
        L.append("")
        L.append("-" * 64)
        L.append(f"ВСЁ ДО {money(maxp)} (от дешёвых к дорогим)")
        cheap = sorted(
            [r for r in rows if r[2]["price"] is not None and r[2]["price"] <= maxp],
            key=lambda r: r[2]["price"],
        )
        if cheap:
            for s, label, it, change, old in cheap:
                L.append(f"  {money(it['price']):>9}  {it['name']} — {s}")
        else:
            L.append("  (нет предложений в этом диапазоне)")

    changes = [r for r in rows if r[3] is not None]
    L.append("")
    L.append("-" * 64)
    if changes:
        L.append(f"ИЗМЕНЕНИЯ: {len(changes)}")
        for s, label, it, change, old in changes:
            arrow = "↓" if change < 0 else "↑"
            L.append(f"  {arrow} {it['name']}: {money(old.get('price'))} -> {money(it['price'])}")
    else:
        L.append("ИЗМЕНЕНИЙ ЦЕН НЕТ.")
    if errors:
        L.append("")
        L.append("ОШИБКИ:")
        for e in errors:
            L.append(f"  ! {e}")
    L.append("")
    report = "\n".join(L)

    # ---- save
    os.makedirs(REPORTS, exist_ok=True)
    fname = "report_" + now.strftime("%Y-%m-%d_%H%M") + ".txt"
    with open(os.path.join(REPORTS, fname), "w", encoding="utf-8") as f:
        f.write(report)
    with open(os.path.join(REPORTS, "latest.txt"), "w", encoding="utf-8") as f:
        f.write(report)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    new_file = not os.path.exists(HISTORY)
    with open(HISTORY, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if new_file:
            w.writerow(["datetime", "site", "label", "name", "price",
                        "availability", "url", "sku"])
        for s, label, it, change, old in rows:
            w.writerow([now.strftime("%Y-%m-%d %H:%M"), s, label,
                        it["name"], it["price"], it["availability"],
                        it["url"], it["sku"]])

    print(report)


if __name__ == "__main__":
    main()
