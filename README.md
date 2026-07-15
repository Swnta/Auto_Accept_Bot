# AutoAccept Bot | Secret Shop

Desktop helper for Dota 2: watches for the **ACCEPT** button, can click it for you, and sends Telegram alerts when a match is found / accepted.

---

## На русском

### Что это
Бот для Dota 2: следит за кнопкой **«ПРИНЯТЬ»**, может сам её нажать и пишет в Telegram, что игра найдена / принята.

### Что нужно
- Windows 10/11  
- Python 3.11+ (если запускаешь из исходников)  
- Dota 2 в оконном / безрамочном режиме, чтобы кнопка «ПРИНЯТЬ» была видна на экране  

### Запуск из исходников
```bash
pip install -r requirements.txt
python src/main.py
```

### Сборка exe
```bash
python tools/build.py
```
Готовый файл появится в корне проекта: `Auto_Accept_Bot.exe`.

Или скачай готовый `.exe` во вкладке **Releases** этого репозитория.

### Настройки
Сохраняются рядом с программой в `settings.json` (токен, Chat ID, галочки).  
Файл в git **не попадает** — **никогда не выкладывай свой Telegram-токен**.

### Telegram (кратко)
1. Создай бота у [@BotFather](https://t.me/BotFather), скопируй токен  
2. Напиши боту, узнай свой Chat ID (например через [@userinfobot](https://t.me/userinfobot))  
3. Вставь Token и Chat ID в настройках приложения и включи Telegram  

### Важно
Неофициальный фан-инструмент. Используй на свой страх и риск и соблюдай правила Steam / Dota 2.

---

## Features

- Auto-detects the green «ПРИНЯТЬ» button on screen
- Optional auto-accept click
- Telegram notifications (+ optional screenshot)
- Lightweight custom UI (Secret Shop)

## Requirements

- Windows 10/11
- Python 3.11+ (to run from source)
- Dota 2 in windowed / borderless so the Accept button is visible on screen

## Install (from source)

```bash
pip install -r requirements.txt
python src/main.py
```

## Build `.exe`

```bash
python tools/build.py
```

The executable appears as `Auto_Accept_Bot.exe` in the project root.

You can also download a ready `.exe` from the **Releases** tab.

## Settings

Settings are saved next to the exe / project as `settings.json` (token, chat id, toggles).  
That file is ignored by git — **never commit your Telegram bot token**.

## Telegram setup (short)

1. Create a bot via [@BotFather](https://t.me/BotFather), copy the token  
2. Write something to your bot, get your Chat ID (e.g. via [@userinfobot](https://t.me/userinfobot))  
3. Paste Token + Chat ID in the app settings and enable Telegram  

## Disclaimer

This project is an unofficial fan tool. Use it at your own risk and follow Steam / Dota 2 rules.

## Author

Secret Shop · GitHub: [Swnta](https://github.com/Swnta)
