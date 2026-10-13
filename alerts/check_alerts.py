# -*- coding: utf-8 -*-
"""
Сторож мониторинга.
 - Отопление (gr=16, cels): если значение упало ниже 40 C -> 1 сообщение.
 - qoltec (gr=22, val): если СРЕДНЕЕ за 30 минут ниже 52.5 В -> 1 сообщение.
   Усреднение нужно, чтобы кратковременные просадки от включения
   тяжёлой техники не давали ложных алертов.

Одноразово: шлём при пересечении порога; снова — только когда значение
вернётся выше порога с запасом (rearm).

Запуск:
  python check_alerts.py        -> обычный прогон (раз в 5 минут, по планировщику)
  python check_alerts.py --test -> прислать тестовое сообщение "сторож работает"
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
VALS_JSON = r"D:\_d\voltage\vals.json"
API = "http://192.168.88.171:90/getdots"
STATE_FILE = os.path.join(BASE, "state.json")
LOG_FILE = os.path.join(BASE, "alerts.log")

FALLBACK_CHAT = 5002583838  # личный диалог (страховка, пока группа не восстановлена)

# mode: "last" — последний замер; "avg30" — среднее за 30 минут (окно 30 мин)
SENSORS = {
    "otoplenie": {
        "gr": 16, "col": "cels", "mode": "last",
        "below": 40.0, "rearm": 41.0,
        "label": "Отопление (теплоноситель)", "unit": "C",
        "src_desc": "последний замер",
    },
    "qoltec": {
        "gr": 22, "col": "val", "mode": "avg30",
        "below": 52.5, "rearm": 52.8,
        "label": "qoltec (вольты)", "unit": "В",
        "src_desc": "среднее за 30 мин",
    },
}


def log(msg):
    line = "%s  %s" % (time.strftime("%d.%m.%Y %H:%M:%S"), msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_vals():
    with open(VALS_JSON, encoding="utf-8") as f:
        return json.load(f)


def get_chat():
    """id чата для алертов из vals.json (PROD.channel)."""
    return int(load_vals()["teleGa"]["PROD"]["channel"])


def get_token():
    return load_vals()["teleGa"]["PROD"]["token"]


def send_tg(token, text):
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    for chat in (get_chat(), FALLBACK_CHAT):
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
                resp = json.load(r)
            if resp.get("ok"):
                log("send_tg: чат %s — ok" % chat)
                return resp
        except Exception as e:
            log("send_tg: чат %s — ошибка: %s" % (chat, e))
    return {"ok": False}


def fetch_values(gr, col, back, gscoef):
    params = urllib.parse.urlencode({"gr": gr, "col": col, "back": back, "gsCoef": gscoef})
    with urllib.request.urlopen(API + "?" + params, timeout=20) as r:
        rows = json.load(r)
    return [row["val"] for row in rows]


def sensor_value(s):
    """Значение датчика: последний замер или среднее за 30 минут."""
    if s["mode"] == "avg30":
        vals = fetch_values(s["gr"], s["col"], 30, 2000)
        if not vals:
            return None
        return sum(vals) / len(vals)
    vals = fetch_values(s["gr"], s["col"], 5, 30)
    if not vals:
        return None
    return vals[-1]


def main():
    token = get_token()

    if "--test" in sys.argv:
        send_tg(token, "Сторож мониторинга работает."
                       " Пороги: отопление < 40 C (последний замер);"
                       " qoltec — среднее за 30 мин < 52.5 В.")
        return

    state = load_state()
    for key, s in SENSORS.items():
        val = sensor_value(s)
        if val is None:
            log("[%s] нет данных — пропуск" % s["label"])
            continue
        cur = state.get(key, "?")
        if cur == "?":
            state[key] = "alerted" if val < s["below"] else "ok"
            log("[%s] инициализация (%s) %.2f %s -> %s (без алерта)"
                % (s["label"], s["src_desc"], val, s["unit"], state[key]))
        elif cur == "ok" and val < s["below"]:
            text = "⚠️ %s: %s ниже %s %s — сейчас %.2f %s" % (
                s["label"], s["src_desc"], s["below"], s["unit"], val, s["unit"])
            try:
                r = send_tg(token, text)
                if r.get("ok"):
                    state[key] = "alerted"
                log("[%s] АЛЕРТ (%s %.2f %s): %s" % (s["label"], s["src_desc"], val, s["unit"], r.get("ok")))
            except Exception as e:
                log("[%s] ОШИБКА отправки: %s" % (s["label"], e))
        elif cur == "alerted" and val >= s["rearm"]:
            state[key] = "ok"
            log("[%s] вернулся выше %s %s (%.2f) — алерт переоткрыт"
                % (s["label"], s["rearm"], s["unit"], val))
        else:
            log("[%s] %s: %.2f %s, состояние %s — без действий"
                % (s["label"], s["src_desc"], val, s["unit"], state.get(key)))
    save_state(state)


if __name__ == "__main__":
    main()