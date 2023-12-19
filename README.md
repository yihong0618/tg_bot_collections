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

![telegram-cloud-photo-size-5-6336976091083817765-y](https://github.com/yihong0618/tg_bot_collections/assets/15976103/683a9c22-6f64-4a51-93e6-5e36218e1668)

## HOW TO Install and Run

### Run with systemd service with Python virtualenv environment

1. Git clone this repo
2. cd tg_bot_collections
3. Copy file .env.example to .env 
4. Edit .env file and change the following variables
    - Google_Gemini_API_Key (Google Gemini API KEY)
    - Telegram_Bot_Token (Telegram Bot Token)
    - Python_Bin_Path (If you install python alternative version, you can use this to specify the python bin path. Default is blank or /usr/bin/python3)
    - Python_Venv_Path (Python virtualenv path. Default is venv)

5. Run ```chmod +x setup.sh && ./setup.sh``` or ``` bash setup.sh 1 ``` to install and run
6. Next time, you can run ```./setup.sh``` or ``` bash setup.sh ``` to restart / stop the tg_bot_collections service and check the status or log
7. you can also run ```./setup.sh 4 ``` to restart service, ```./setup.sh 5 ``` to stop, ```./setup.sh 7 ``` to check the log

### Run with command line with Python virtualenv environment
1. Git clone this repo
2. cd tg_bot_collections
3. Copy file .env.example to .env 
4. Edit .env file and change the following variables (Same as above that Run with systemd service)
5. Run ```chmod +x setup.sh && ./setup.sh``` or ``` bash setup.sh 2 ``` to install and run
6. Ctrl + C to quit and Run ```deactivate``` to exit the virtualenv environment
7. Next time, you can run ```./setup.sh``` or ``` bash setup.sh ``` to restart / stop the tg_bot_collections service and check the status or log

### Manually install 
1. pip install -r requirements.txt
2. Get tg token, ask Google or ChatGPT, need get it from [BotFather](https://t.me/BotFather)
3. export GOOGLE_GEMINI_KEY=${your_google_gemini_apikey}
4. python tg.py ${telegram_bot_token}

### Run from Docker
1. docker build -t tg_bot_collections .
2. docker run -d --name tg_bot_collections -e GOOGLE_GEMINI_KEY='${GOOGLE_GEMINI_KEY}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections


## HOW TO Use

1. Type `/gemini: ${message}` to ask
2. Type `gemini: ${message}` and upload picture to ask with picture

> [!Note]
> If you don't want to use one of these command, you can use `--disable-command <command>` option to disable it. This option can be used multiple times.


## Contribution

- Any issue reports or PRs are welcome.
- Before PR, use `pip install -U black` then `black .` first

## Acknowledge

- poster use my repo -> https://github.com/yihong0618/GitHubPoster
- pretty map use wonder repo -> https://github.com/chrieke/prettymapp
- Gemini use -> https://github.com/google/generative-ai-python
- Telegram markdownV2 change code copy from https://github.com/yym68686/md2tgmd/blob/main/src/md2tgmd.py thanks a lot.

## Appreciation

- Thank you, that's enough. Just enjoy it.
