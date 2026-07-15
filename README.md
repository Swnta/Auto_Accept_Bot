# AutoAccept Bot | Secret Shop

Desktop helper for Dota 2: watches for the **ACCEPT** button, can click it for you, and sends Telegram alerts when a match is found / accepted.

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
