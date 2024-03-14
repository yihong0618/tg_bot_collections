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


## Bot -> Claude 3

1. visit https://console.anthropic.com/ get the key
2. export ANTHROPIC_API_KEY=${the_key}
3. use `claude: ${message}` to ask

Note, if you are using third party service, you need to `export ANTHROPIC_BASE_URL=${the_url}` to change the url.


## HOW TO Install and Run

### Manually install 
1. pip install -r requirements.txt
2. Get tg token, ask Google or ChatGPT, need get it from [BotFather](https://t.me/BotFather)
3. export GOOGLE_GEMINI_KEY=${your_google_gemini_apikey}
4. python tg.py ${telegram_bot_token}

### Run from Docker
1. docker build -t tg_bot_collections .
2. docker run -d --name tg_bot_collections -e GOOGLE_GEMINI_KEY='${GOOGLE_GEMINI_KEY}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections

### Run as shell

Note, this may break your system config -> check this https://github.com/yihong0618/tg_bot_collections/issues/5


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
