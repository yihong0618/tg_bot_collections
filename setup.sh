#!/bin/bash

python_bin_path="/usr/local/bin/python3.10"
venv_dir="venv"

project_path="/root/github/tg_bot_collections"

GOOGLE_GEMINI_KEY_Text="xxx"
Telegram_Bot_KEY_Text="xxx"





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

# 检测系统发行版代号
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
        osReleaseVersionCodeName="bionic"
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




cat > ${osSystemMdPath}tgbotgemini.service <<-EOF

[Unit]
Description=tgbotgemini service
After=network.target

[Service]
User=root
Group=root

Environment="GOOGLE_GEMINI_KEY=${GOOGLE_GEMINI_KEY_Text}"

WorkingDirectory=$project_path
ExecStart=$project_path/venv/bin/python $project_path/tg.py "${Telegram_Bot_KEY_Text}"

Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF


chmod +x ${osSystemMdPath}tgbotgemini.service
systemctl daemon-reload
systemctl start tgbotgemini.service

echo "Run following command to start / stop telegram bot"
echo "Start: systemctl start tgbotgemini.service"
echo "Stop: systemctl stop tgbotgemini.service"
echo "Check running status: systemctl status tgbotgemini.service"
