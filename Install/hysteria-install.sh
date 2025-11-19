#!/bin/bash
# Hysteria Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m    Hysteria Installation Script\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if Hysteria is installed
if [[ -e /etc/hysteria/config.json ]]; then
    echo -e "\033[1;33mHysteria is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Uninstall Hysteria"
    echo -e "[3] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nCurrent Configuration:\033[0m"
            cat /etc/hysteria/config.json
            exit 0
            ;;
        2)
            echo -e "\033[1;31mUninstalling Hysteria...\033[0m"
            systemctl stop hysteria-server
            systemctl disable hysteria-server
            rm -rf /etc/hysteria
            rm -f /usr/local/bin/hysteria
            echo -e "\033[1;32mHysteria uninstalled successfully!\033[0m"
            exit 0
            ;;
        3)
            exit 0
            ;;
    esac
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for port
read -p "Enter port (default 36712): " PORT
PORT=${PORT:-36712}

# Generate password
PASSWORD=$(openssl rand -base64 16)

# Install Hysteria
echo -e "\033[1;36mDownloading Hysteria...\033[0m"
wget -O /usr/local/bin/hysteria https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64
chmod +x /usr/local/bin/hysteria

# Create configuration directory
mkdir -p /etc/hysteria

# Generate self-signed certificate
echo -e "\033[1;36mGenerating SSL certificate...\033[0m"
openssl req -x509 -nodes -newkey rsa:2048 -keyout /etc/hysteria/server.key -out /etc/hysteria/server.crt -days 365 -subj "/CN=$SERVER_IP"

# Create server configuration
cat > /etc/hysteria/config.json <<EOF
{
  "listen": ":$PORT",
  "cert": "/etc/hysteria/server.crt",
  "key": "/etc/hysteria/server.key",
  "obfs": "$PASSWORD",
  "up_mbps": 100,
  "down_mbps": 100,
  "disable_udp": false,
  "acl": {
    "inline": [
      "reject(geoip:cn)",
      "reject(geosite:cn)"
    ]
  },
  "auth": {
    "mode": "password",
    "config": {
      "password": "$PASSWORD"
    }
  }
}
EOF

# Create systemd service
cat > /etc/systemd/system/hysteria-server.service <<EOF
[Unit]
Description=Hysteria Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/hysteria
ExecStart=/usr/local/bin/hysteria server -c /etc/hysteria/config.json
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable hysteria-server
systemctl start hysteria-server

# Open firewall
ufw allow $PORT/udp 2>/dev/null
ufw allow $PORT/tcp 2>/dev/null

# Create client configuration
cat > /etc/hysteria/client.json <<EOF
{
  "server": "$SERVER_IP:$PORT",
  "obfs": "$PASSWORD",
  "auth_str": "$PASSWORD",
  "up_mbps": 100,
  "down_mbps": 100,
  "socks5": {
    "listen": "127.0.0.1:1080"
  },
  "http": {
    "listen": "127.0.0.1:8080"
  }
}
EOF

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m  Hysteria installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mPort: $PORT (UDP/TCP)\033[0m"
echo -e "\033[1;33mPassword: $PASSWORD\033[0m"
echo -e "\033[1;33mSpeed: 100/100 Mbps\033[0m"
echo ""
echo -e "\033[1;36mClient configuration saved at: /etc/hysteria/client.json\033[0m"
echo ""
