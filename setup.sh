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

if [ -n "$Python_Venv_Path" ]; then
    venv_dir="${Python_Venv_Path}"
fi

if [ -n "$Python_Bin_Path" ]; then
    python_bin_path="$Python_Bin_Path"
fi

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

function installPythonVirtualEnv(){
    echo
    echo "=============================="
    echo "Prapare to Install telegram bot"
    echo
    echo "Project path: $project_path"
    echo "Python bin path: $python_bin_path"
    echo "Google_Gemini_API_Key: $Google_Gemini_API_Key"
    echo "Telegram Bot Token: $Telegram_Bot_Token"
    echo

    # Check Virtual Environment exist
    if [ -d "$venv_dir" ]; then
        echo "Virtual Environment already exist"
        if [ -z "$1" ]; then
            exit 1
        else
            source $venv_dir/bin/activate
        fi
    else
        # created virtual environment
        echo "Creating virtual environment..."
        $python_bin_path -m venv "$venv_dir"

        if [ $? -eq 0 ]; then
            echo "Successfully created virtual environment."

            source $venv_dir/bin/activate
            python -m pip install --upgrade pip
            pip install -r requirements.txt
        else
            echo "Failed to create virtual environment."
            exit 1
        fi
    fi
}

function installSystemd(){
    installPythonVirtualEnv

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
    ${sudoCmd} systemctl enable ${service_name}.service
    ${sudoCmd} systemctl start ${service_name}.service

    echo
    echo "${service_name}.service running successfully"
    echo
    echo "Run following command to start / stop telegram bot"
    echo "Start: systemctl start ${service_name}.service"
    echo "Stop: systemctl stop ${service_name}.service"
    echo "Check running status: systemctl status ${service_name}.service"
    echo "=============================="
}
function uninstallSystemd(){
    ${sudoCmd} systemctl stop ${service_name}.service
    ${sudoCmd} systemctl disable ${service_name}.service
    ${sudoCmd} rm -rf ${osSystemMdPath}${service_name}.service
    ${sudoCmd} systemctl daemon-reload
}

function installCommandLine(){
    installPythonVirtualEnv "noexit"

    echo
    echo "=============================="
    export GOOGLE_GEMINI_KEY=$google_gemini_api_key
    python tg.py "${telegram_bot_token}"
}

function runSystemd(){
    echo
    if [ "$1" == "start" ]; then
        echo "systemctl start ${service_name}.service"
        ${sudoCmd} systemctl start ${service_name}.service

    elif [ "$1" == "restart" ]; then
        echo "systemctl restart ${service_name}.service"
        ${sudoCmd} systemctl restart ${service_name}.service

    elif [ "$1" == "stop" ]; then
        echo "systemctl stop ${service_name}.service"
        ${sudoCmd} systemctl stop ${service_name}.service

    elif [ "$1" == "status" ]; then
        echo "systemctl status ${service_name}.service"
        ${sudoCmd} systemctl status ${service_name}.service

    else
        echo "journalctl -n 30 -u ${service_name}.service "
        ${sudoCmd} journalctl -n 30 -u ${service_name}.service
    fi
    echo
}

function start_menu(){
    clear

    echo "=============================="
    echo " 1. Install telegram bot and Run with Systemd Service"
    echo " 2. Install and Run with Command Line"
    echo
    echo " 3. Uninstall telegram bot and Systemd Service"
    echo
    echo " 4. Restart ${service_name} Systemd Service"
    echo " 5. Stop ${service_name} Systemd Service"
    echo " 6. Check Status of ${service_name} Systemd Service"
    echo " 7. Show Log of ${service_name} Systemd Service"
    echo
    echo " 0. exit"

    echo
    read -r -p "Please input number:" menuNumberInput
    case "$menuNumberInput" in
        1 )
            installSystemd
        ;;
        2 )
            installCommandLine
        ;;
        3 )
            uninstallSystemd
        ;;
        4 )
            runSystemd "restart"
        ;;
        5 )
            runSystemd "stop"
        ;;
        6 )
            runSystemd "status"
        ;;
        7 )
            runSystemd
        ;;
        0 )
            exit 1
        ;;
        * )
            clear
            echo "Please input correct number !"
            sleep 2s
            start_menu
        ;;
    esac
}

function showMenu(){

        if [ -z "$1" ]; then
            start_menu
        elif [ "$1" == "1" ]; then
            installSystemd
        elif [ "$1" == "2" ]; then
            installCommandLine
        elif [ "$1" == "3" ]; then
            uninstallSystemd
        elif [ "$1" == "4" ]; then
            runSystemd "restart"
        elif [ "$1" == "5" ]; then
            runSystemd "stop"
        elif [ "$1" == "6" ]; then
            runSystemd "status"
        elif [ "$1" == "7" ]; then
            runSystemd
        else
            start_menu
        fi
}

showMenu $1