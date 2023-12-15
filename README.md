# tg_bot_collections
Collections of yihong0618's telegram bot

for yihong0618's channel: https://t.me/hyi0618


## Bot -> poster

![image](https://github.com/yihong0618/tg_bot_collections/assets/15976103/6cf6b2c0-9f43-42f4-ba5f-be768ea27fd1)

## Bot -> pretty mapper

![image](https://github.com/yihong0618/tg_bot_collections/assets/15976103/29848d22-5289-4953-8ab0-4e84c16f79e3)


## Bot -> Gemini player

1. visit https://makersuite.google.com/app/apikey get the key
2. export GOOGLE_GEMINI_KEY=${the_key}
3. use `gemini: ${message}` to ask


## HOW TO Install and Run

### Run with systemd service

1. Git clone this repo
2. cd tg_bot_collections
3. Edit setup.sh file and change the following variables
    - python_bin_path (python3 path)
    - project_path (this repo path)
    - GOOGLE_GEMINI_KEY_Text (Google Gemini API KEY)
    - Telegram_Bot_KEY_Text (Telegram Bot Token)
4. Run ```chmod +x setup.sh && ./setup.sh``` or ``` bash setup.sh ```
5. Run ```systemctl status tg_bot_collections``` to check the status
6. Run ```systemctl start tg_bot_collections``` to start the service
7. Run ```systemctl stop tg_bot_collections``` to stop the service

### Manually install 

1. pip install -r requirements.txt
2. Get tg token, ask Google or ChatGPT, need get it from [BotFather](https://t.me/BotFather)
3. export GOOGLE_GEMINI_KEY=${your_google_gemini_apikey}
4. python tg.py ${telegram_bot_token}


## HOW TO Use

1. Type `/gemini: ${message}` to ask
2. Type `gemini: ${message}` and upload picture to ask with picture


## Contribution

- Any issue reports or PRs are welcome.
- Before PR, use `pip install -U black` then `black .` first

## Acknowledge

- poster use my repo -> https://github.com/yihong0618/GitHubPoster
- pretty map use wonder repo -> https://github.com/chrieke/prettymapp
- Gemini use -> https://github.com/google/generative-ai-python

## Appreciation

- Thank you, that's enough. Just enjoy it.

