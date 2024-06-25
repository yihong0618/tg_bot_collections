# tg_bot_collections
Collections of yihong0618's telegram bot

for yihong0618's channel: https://t.me/hyi0618


## Bot -> poster

![image](https://github.com/yihong0618/tg_bot_collections/assets/15976103/6cf6b2c0-9f43-42f4-ba5f-be768ea27fd1)

## Bot -> pretty mapper

![image](https://github.com/yihong0618/tg_bot_collections/assets/15976103/29848d22-5289-4953-8ab0-4e84c16f79e3)


## Bot -> [ChatTTS](https://github.com/2noise/ChatTTS)

2. export USE_CHATTTS=true
3. use `tts: ${message}` to generate


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


## Bot -> lingyiwanwu

1. visit https://platform.lingyiwanwu.com/apikeys get the key
2. export YI_API_KEY=${the_key}
3. export YI_BASE_URL=${the_url}
3. use `yi: ${message}` to ask

![image](https://github.com/yihong0618/tg_bot_collections/assets/15976103/11d96dde-447b-4b7e-886d-c3564e27b0d6)


## Bot -> ChatGPT

1. visit https://platform.openai.com/account/api-keys get the key
2. export OPENAI_API_KEY=${the_key}
3. use `gpt: ${message}` to ask

Note, if you are using third party service, you need to `export OPENAI_API_BASE=${the_url}` to change the url.

## Bot -> llama3

1. visit https://console.groq.com/docs/quickstart get the key
2. export GROQ_API_KEY=${the_key}
3. use `llama_pro: ${message}` to ask

## Bot -> qwen

1. visit https://api.together.xyz/settings/api-keys get the key
2. export TOGETHER_API_KEY=${the_key}
3. use `qwen_pro: ${message}` to ask

## Bot -> dify

1. visit https://cloud.dify.ai/ get selected Chatbot's API Secret key
2. export DIFY_API_KEY=${the_key}
3. use `dify: ${message}` to ask

Note, currently its support dify Chatbot with instructions(System prompt) and different MODEL with its parameters.

## Bot -> Cohere

1. visit https://dashboard.cohere.com/api-keys get the key
2. export COHERE_API_KEY=${the_key}
3. use `cohere: ${message}` to ask

## Function -> Telegraph

### Skip token (default)

You do not need to do anything.

But you may not be able to edit any generated post since you do not have the token.

### Store token (recommended)

Change "Store_Token" to "True" in "handlers/__init__.py" TelegraphAPI/_create_ph_account. It will store the token in "token_key.json".

### Get token manually from Telegram account

1. https://t.me/telegraph Create or login Telegraph account
2. `Log in as ${Account} on this device`
3. On Browser at https://telegra.ph/, press F12 or right click and inspect
4. Go to Application -> Storage -> Cookies -> https://telegra.ph/
5. The token at `tph_token` is the token for telegra.ph API

Do not share the token with others, it's like a password.

## HOW TO Install and Run

### Manually install 
1. pip install -r requirements.txt
2. Get tg token, ask Google or ChatGPT, need get it from [BotFather](https://t.me/BotFather)
3. export GOOGLE_GEMINI_KEY=${your_google_gemini_apikey}
4. python tg.py ${telegram_bot_token}

### Run from Docker
#### build docker image
`docker build -t tg_bot_collections .`
#### Run Gemini
`docker run -d --name tg_bot_collections -e GOOGLE_GEMINI_KEY='${GOOGLE_GEMINI_KEY}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections`
#### Run Claude 3
`docker run -d --name tg_bot_collections -e ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections`
#### Run lingyiwanwu
`docker run -d --name tg_bot_collections -e YI_API_KEY='${YI_API_KEY}' -e YI_BASE_URL='${YI_BASE_URL}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections`
#### Run ChatGPT
`docker run -d --name tg_bot_collections -e OPENAI_API_KEY='${CHATGPT_API_KEY}' -e TELEGRAM_BOT_TOKEN='${TELEGRAM_BOT_TOKEN}' --network host tg_bot_collections`

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
- Telegram markdownV2 change to telegramify-markdown
- ChatGPT use -> https://github.com/openai/openai-python

## Appreciation

- Thank you, that's enough. Just enjoy it.
