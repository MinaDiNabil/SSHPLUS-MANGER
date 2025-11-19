#!/bin/bash
# Shadowsocks-libev Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m  Shadowsocks Installation Script\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if Shadowsocks is installed
if [[ -e /etc/shadowsocks-libev/config.json ]]; then
    echo -e "\033[1;33mShadowsocks is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Change password"
    echo -e "[3] Uninstall Shadowsocks"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nCurrent Configuration:\033[0m"
            cat /etc/shadowsocks-libev/config.json
            exit 0
            ;;
        2)
            read -p "Enter new password: " new_pass
            sed -i "s/\"password\": \".*\"/\"password\": \"$new_pass\"/" /etc/shadowsocks-libev/config.json
            systemctl restart shadowsocks-libev
            echo -e "\033[1;32mPassword changed successfully!\033[0m"
            exit 0
            ;;
        3)
            echo -e "\033[1;31mUninstalling Shadowsocks...\033[0m"
            systemctl stop shadowsocks-libev
            systemctl disable shadowsocks-libev
            apt-get remove --purge -y shadowsocks-libev
            rm -rf /etc/shadowsocks-libev
            echo -e "\033[1;32mShadowsocks uninstalled successfully!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Generate random password
PASS=$(openssl rand -base64 16)

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for port
read -p "Enter port (default 8388): " PORT
PORT=${PORT:-8388}

# Install Shadowsocks
echo -e "\033[1;36mInstalling Shadowsocks-libev...\033[0m"
apt-get update -y
apt-get install -y shadowsocks-libev

# Create configuration directory
mkdir -p /etc/shadowsocks-libev

# Create configuration file
cat > /etc/shadowsocks-libev/config.json <<EOF
{
    "server": "0.0.0.0",
    "server_port": $PORT,
    "password": "$PASS",
    "timeout": 300,
    "method": "aes-256-gcm",
    "fast_open": true,
    "workers": 1,
    "prefer_ipv6": false,
    "mode": "tcp_and_udp"
}
EOF

# Create systemd service
cat > /etc/systemd/system/shadowsocks-libev.service <<EOF
[Unit]
Description=Shadowsocks-libev Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/ss-server -c /etc/shadowsocks-libev/config.json
Restart=on-abort

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable shadowsocks-libev
systemctl start shadowsocks-libev

# Open firewall
ufw allow $PORT/tcp 2>/dev/null
ufw allow $PORT/udp 2>/dev/null

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m Shadowsocks installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mPort: $PORT\033[0m"
echo -e "\033[1;33mPassword: $PASS\033[0m"
echo -e "\033[1;33mEncryption: aes-256-gcm\033[0m"
echo ""
echo -e "\033[1;36mSave this information for client configuration!\033[0m"
echo ""

# Generate QR code URL
SS_LINK="ss://$(echo -n "aes-256-gcm:$PASS" | base64)@$SERVER_IP:$PORT"
echo -e "\033[1;36mConnection Link:\033[0m"
echo "$SS_LINK"
echo ""
