#!/bin/bash

python_bin_path="$(which python3)"

project_path="$(pwd)"
service_name="tgbotyh"

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
echo "Prapare to setup telegram bot"
echo ""
echo "Project path: $project_path"
echo "Python bin path: $python_bin_path"
echo "Google_Gemini_API_Key: $Google_Gemini_API_Key"
echo "Telegram Bot Token: $Telegram_Bot_Token"
echo ""

sudoCmd=""
if [[ $(/usr/bin/id -u) -ne 0 ]]; then
  sudoCmd="sudo"
fi

# Check Virtual Environment exist
if [ -d "$venv_dir" ]; then
    echo "Virtual Environment already exist"
    exit 1
fi

# created virtual environment
$python_bin_path -m venv "$venv_dir"
if [ $? -eq 0 ]; then
    echo "Successfully created virtual environment."
else
    echo "Failed to create virtual environment."
fi

source $venv_dir/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

osSystemMdPath="/lib/systemd/system/"

# Chcek OS release distribution
function getLinuxOSRelease(){
    if [[ -f /etc/redhat-release ]]; then
        osRelease="centos"
        osSystemPackage="yum"
        osSystemMdPath="/usr/lib/systemd/system/"
    elif cat /etc/issue | grep -Eqi "debian|raspbian"; then
        osRelease="debian"
        osSystemPackage="apt-get"
        osSystemMdPath="/lib/systemd/system/"
    elif cat /etc/issue | grep -Eqi "ubuntu"; then
        osRelease="ubuntu"
        osSystemPackage="apt-get"
        osSystemMdPath="/lib/systemd/system/"
    elif cat /etc/issue | grep -Eqi "centos|red hat|redhat"; then
        osRelease="centos"
        osSystemPackage="yum"
        osSystemMdPath="/usr/lib/systemd/system/"
    elif cat /proc/version | grep -Eqi "debian|raspbian"; then
        osRelease="debian"
        osSystemPackage="apt-get"
        osSystemMdPath="/lib/systemd/system/"
    elif cat /proc/version | grep -Eqi "ubuntu"; then
        osRelease="ubuntu"
        osSystemPackage="apt-get"
        osSystemMdPath="/lib/systemd/system/"
    elif cat /proc/version | grep -Eqi "centos|red hat|redhat"; then
        osRelease="centos"
        osSystemPackage="yum"
        osSystemMdPath="/usr/lib/systemd/system/"
    fi

}

cat > ${osSystemMdPath}${service_name}.service <<-EOF

[Unit]
Description=$service_name service
After=network.target

[Service]
User=root
Group=root

Environment="GOOGLE_GEMINI_KEY=${google_gemini_api_key}"

WorkingDirectory=$project_path
ExecStart=$project_path/venv/bin/python $project_path/tg.py "${telegram_bot_token}"

Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

${sudoCmd} chmod +x ${osSystemMdPath}${service_name}.service
${sudoCmd} systemctl daemon-reload
${sudoCmd} systemctl start ${service_name}.service

echo ""
echo "${service_name}.service running successfully" 
echo ""
echo "Run following command to start / stop telegram bot"
echo "Start: systemctl start ${service_name}.service"
echo "Stop: systemctl stop ${service_name}.service"
echo "Check running status: systemctl status ${service_name}.service"
echo "=============================="
