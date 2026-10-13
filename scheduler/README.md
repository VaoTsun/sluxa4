# Планировщик задач OpenCode

Механизм, который позволяет запускать задачи по расписанию через встроенный
**Планировщик заданий Windows** (ничего скачивать не нужно).

## Папки

```
d:\_d\sluxach\scheduler\
  run.ps1          - запускает одну задачу и пишет лог
  schedule.ps1     - создаёт / удаляет / показывает задачи в Планировщике
  tasks\           - сами задачи: <имя>.ps1 | <имя>.py | <имя>.cmd
  logs\            - результаты запусков: <имя>.log (UTF-8)
```

## Как создать задачу

1. Положить скрипт задачи в `tasks\<имя>.ps1` (или `.py`, или `.cmd`).
2. Прописать её в Планировщике.

### Ежедневно в заданное время

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File d:\_d\sluxach\scheduler\schedule.ps1 `
  -Action add -Name prices -Time 09:00
```

Под этим именем в Планировщике появится задача `OpenCode-prices`. Она запускает
`run.ps1 -Name prices`, который выполняет `tasks\prices.ps1` и пишет результат в
`logs\prices.log`.

### Каждые N минут (для тестов)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File d:\_d\sluxach\scheduler\schedule.ps1 `
  -Action add -Name test -Minutes 5
```

## Управление

```powershell
# список задач
schedule.ps1 -Action list

# запустить прямо сейчас (не дожидаясь расписания)
schedule.ps1 -Action run -Name prices

# удалить
schedule.ps1 -Action remove -Name prices
```

## Задача «prices» — цены на роботы-газонокосилки

Ежедневно в **09:00** проверяет цены на роботы-газонокосилки (в т.ч. GUST 550
со снежным отвалом). Магазины:

- `kelmestechnika.lt` — GUST 550 (со снежным отвалом и без);
- `martynotechnika.lt` — роботы GTM (50 PRO, 90 PRO, GT 80 PRO);
- `kainos.lt` — агрегатор цен: **сам находит предложения других магазинов**
  (Toolsta.lt и др.) и товары со снежным модулем (Yarbo у Varle.lt /
  Vejos-robotai.lt);
- `skelbiu.lt` — доска объявлений (б/у). Отчёт дополнительно содержит раздел
  «ВСЁ ДО 2 500 €» — порог задаётся полем `max_price` в `targets.json`.

Скрипт: `d:\_d\sluxach\prices\check_prices.py`,
список сайтов и товаров: `d:\_d\sluxach\prices\targets.json`.

Результаты:

- `d:\_d\sluxach\prices\reports\latest.txt` — последний отчёт;
- `d:\_d\sluxach\prices\reports\report_*.txt` — отчёты по датам;
- `d:\_d\sluxach\prices\history.csv` — история цен;
- `logs\prices.log` — лог запусков.

Изменить время запуска (повторный `add` перезаписывает задачу):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File d:\_d\sluxach\scheduler\schedule.ps1 `
  -Action add -Name prices -Time 08:30
```

## Как это устроено

- Задача Планировщика = `powershell.exe -File run.ps1 -Name <имя>`.
- `run.ps1` находит файл задачи по имени, выполняет его, пишет stdout/stderr
  и отметку времени в `logs\<имя>.log`.
- Имя задачи в Планировщике всегда с префиксом `OpenCode-`, чтобы не путать с
  системными задачами.

## Заметки

- Задача выполняется от имени текущего пользователя, пока он вошёл в систему.
- Если нужно «даже когда пользователь не в системе» — понадобится пароль учётной
  записи (управляется в свойствах задачи Планировщика).
- Питон-задачи запускаются как `python -X utf8 <файл>`; для русского вывода
  кодировка UTF-8.
