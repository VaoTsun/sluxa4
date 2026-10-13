# sluxach — голосовой ассистент «Подружка»

Локальный голосовой ассистент: распознавание речи (Vosk, русская модель),
запуск приложений/навыков по команде после слова **«подружка»**, режим диктовки,
чтение ответа DeepSeek через OCR + озвучку (голос Irina, SAPI).

## Состав

| Файл | Назначение |
| --- | --- |
| `assistant.py.txt` | основной скрипт ассистента (запуск: `python assistant.py.txt`) |
| `plot_heating.py` | график отопления → `otoplenie_5h.html` |
| `read_deepseek_window.ps1` | снимок окна DeepSeek + OCR |
| `status_window.ps1` | окно прогресса загрузки (за `status.txt`) |
| `plan.txt` | план дня (редактируется командой «подружка навык план …») |
| `alerts/`, `prices/`, `scheduler/` | вспомогательные скрипты-обработчики |
| `vosk-model-ru-0.42/` | модель распознавания (в git **не** хранится, ~3,4 ГБ, ~5 ГБ RAM) |

## Запуск

### Windows
```powershell
python -m pip install sounddevice vosk
python assistant.py.txt
```
Нужна модель Vosk `vosk-model-ru-0.42` рядом со скриптом
(или `vosk-model-small-ru-0.22` с правкой `MODEL_PATH`).

### Работа с кодом из Linux (через OpenCode)
```bash
git clone https://github.com/VaoTsun/sluxa4.git
cd sluxa4
opencode
```
Сам ассистент завязан на Windows (winsound, PowerShell TTS/OCR),
но файлы кода и конфиги скриптов редактируются из любой ОС.

## Примечания
- Модели, логи, рантайм-состояние (`*.log`, `*.err`, `state.json`,
  `prices/reports/`, `status.txt`) в git не хранятся — см. `.gitignore`.