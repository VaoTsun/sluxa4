# -*- coding: utf-8 -*-
"""Строит график температуры отопления за последние N минут (по умолчанию 300)."""
import json
import os
import sys
import datetime
import urllib.request

BASE = "http://192.168.88.171:90"
GR = 16
COL = "cels"
MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 300

URL = f"{BASE}/getdots?gr={GR}&col={COL}&back={MINUTES}&gsCoef=100"
raw = urllib.request.urlopen(URL, timeout=30).read().decode("utf-8")
data = json.loads(raw)


def parse_ts(t):
    return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ")


pts = sorted((parse_ts(p["ts"]), float(p["val"])) for p in data)
t0, t1 = pts[0][0], pts[-1][0]
vals = [v for _, v in pts]
vmin, vmax = min(vals), max(vals)
span = (t1 - t0).total_seconds() / 60

print(f"Точек: {len(pts)}")
print(f"Период: {t0:%H:%M} - {t1:%H:%M} (~{span:.0f} мин)")
print(f"Мин: {vmin:g} | Макс: {vmax:g} | Сейчас: {vals[-1]:g}")
print(f"Изменение: {vals[-1] - vals[0]:+.2f}")

# ---------- текстовая диаграмма ----------
W, H = 62, 13
grid = [[" "] * W for _ in range(H)]
n = len(pts)
for i, (dt, v) in enumerate(pts):
    x = 0 if n == 1 else int(round(i * (W - 1) / (n - 1)))
    y = H // 2 if vmax == vmin else int(round((vmax - v) * (H - 1) / (vmax - vmin)))
    grid[y][x] = "*"
print()
for r in range(H):
    vlab = vmax - (vmax - vmin) * r / (H - 1)
    print(f"{vlab:5.1f} |" + "".join(grid[r]))
print("      +" + "-" * W)
print("       " + f"{t0:%H:%M}" + " " * (W - 12) + f"{t1:%H:%M}")

# ---------- SVG-график ----------
Wp, Hp = 1000, 430
padL, padR, padT, padB = 70, 30, 50, 60
plotW, plotH = Wp - padL - padR, Hp - padT - padB
xmax = (t1 - t0).total_seconds() or 1
ymin, ymax = vmin - 1, vmax + 1


def X(dt):
    return padL + (dt - t0).total_seconds() / xmax * plotW


def Y(v):
    return padT + (ymax - v) / (ymax - ymin) * plotH


s = []
s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wp}" height="{Hp}" '
         f'font-family="Segoe UI, Arial, sans-serif">')
s.append(f'<rect width="{Wp}" height="{Hp}" fill="#ffffff"/>')
s.append(f'<text x="{Wp/2}" y="28" text-anchor="middle" font-size="20" '
         f'font-weight="600">Отопление — температура теплоносителя '
         f'({t0:%H:%M}–{t1:%H:%M})</text>')
for k in range(7):
    v = ymin + (ymax - ymin) * k / 6
    y = Y(v)
    s.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{padL+plotW}" y2="{y:.1f}" stroke="#ececec"/>')
    s.append(f'<text x="{padL-8}" y="{y+4:.1f}" text-anchor="end" font-size="12" fill="#777">{v:.0f}°</text>')
cur = t0.replace(minute=0, second=0, microsecond=0)
if cur < t0:
    cur += datetime.timedelta(hours=1)
while cur <= t1:
    x = X(cur)
    s.append(f'<line x1="{x:.1f}" y1="{padT}" x2="{x:.1f}" y2="{padT+plotH}" stroke="#f4f4f4"/>')
    s.append(f'<text x="{x:.1f}" y="{padT+plotH+20}" text-anchor="middle" font-size="12" fill="#777">{cur:%H:%M}</text>')
    cur += datetime.timedelta(hours=1)
s.append(f'<line x1="{padL}" y1="{padT}" x2="{padL}" y2="{padT+plotH}" stroke="#999"/>')
s.append(f'<line x1="{padL}" y1="{padT+plotH}" x2="{padL+plotW}" y2="{padT+plotH}" stroke="#999"/>')
poly = " ".join(f"{X(dt):.1f},{Y(v):.1f}" for dt, v in pts)
s.append(f'<polyline points="{poly}" fill="none" stroke="#e53935" stroke-width="2.5"/>')
for dt, v in pts:
    s.append(f'<circle cx="{X(dt):.1f}" cy="{Y(v):.1f}" r="3" fill="#e53935"/>')
lx, ly = X(pts[-1][0]), Y(pts[-1][1])
s.append(f'<text x="{lx-6:.1f}" y="{ly-10:.1f}" text-anchor="end" font-size="15" '
         f'font-weight="700" fill="#e53935">{vals[-1]:g}°C</text>')
s.append(f'<text x="{padL}" y="{Hp-12}" font-size="12" fill="#999">'
         f'мин {vmin:g}°C · макс {vmax:g}°C · точек {len(pts)} · данные monitoring '
         f'{BASE}</text>')
s.append('</svg>')

html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<title>Отопление — 5 часов</title></head>'
        '<body style="margin:0;background:#fff">' + "".join(s) + '</body></html>')

out = r"d:\_d\sluxach\otoplenie_5h.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("\nСохранено:", out)
os.startfile(out)
