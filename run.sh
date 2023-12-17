#!/bin/bash

python_bin_path="$(which python3)"
venv_dir="venv"
project_path="$(pwd)"

source .env

google_gemini_api_key="${Google_Gemini_API_Key}"
telegram_bot_token="${Telegram_Bot_Token}"

if [ -n "$Python_Venv_Path" ]; then
    venv_dir="${Python_Venv_Path}"
fi

if [ -n "$Python_Bin_Path" ]; then
    python_bin_path="$Python_Bin_Path"
fi

echo "=============================="
echo "Prapare to run telegram bot"
echo ""
echo "Project path: $project_path"
echo "Python bin path: $python_bin_path"
echo "Google_Gemini_API_Key: $Google_Gemini_API_Key"
echo "Telegram Bot Token: $Telegram_Bot_Token"
echo ""

# Check Virtual Environment exist
if [ -d "$venv_dir" ]; then
    echo "Virtual Environment already exist"
    source $venv_dir/bin/activate
else
    # created virtual environment
    echo "Creating virtual environment..."
    $python_bin_path -m venv "$venv_dir"

    if [ $? -eq 0 ]; then
        echo "Successfully created virtual environment."
    else
        echo "Failed to create virtual environment."
    fi

    source $venv_dir/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
fi

echo "=============================="
export GOOGLE_GEMINI_KEY=$google_gemini_api_key
python tg.py "${telegram_bot_token}"
