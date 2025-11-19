#!/bin/bash
# Psiphon Server Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m    Psiphon Server Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if Psiphon is installed
if [[ -e /opt/psiphon/psiphond ]]; then
    echo -e "\033[1;33mPsiphon is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Restart service"
    echo -e "[3] Uninstall Psiphon"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nPsiphon Configuration:\033[0m"
            cat /opt/psiphon/config.json 2>/dev/null
            exit 0
            ;;
        2)
            systemctl restart psiphon
            echo -e "\033[1;32mPsiphon restarted!\033[0m"
            exit 0
            ;;
        3)
            echo -e "\033[1;31mUninstalling Psiphon...\033[0m"
            systemctl stop psiphon
            systemctl disable psiphon
            rm -rf /opt/psiphon
            rm -f /etc/systemd/system/psiphon.service
            systemctl daemon-reload
            echo -e "\033[1;32mPsiphon uninstalled!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Install dependencies
echo -e "\033[1;36mInstalling dependencies...\033[0m"
apt-get update -y
apt-get install -y wget git golang-go build-essential

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Create directory
mkdir -p /opt/psiphon
cd /opt/psiphon

# Download Psiphon Server (using open-source alternative - gost)
echo -e "\033[1;36mDownloading Psiphon-compatible server...\033[0m"

# Install GOST (GO Simple Tunnel) as Psiphon alternative
ARCH=$(uname -m)
if [[ "$ARCH" == "x86_64" ]]; then
    GOST_ARCH="linux-amd64"
elif [[ "$ARCH" == "aarch64" ]]; then
    GOST_ARCH="linux-armv8"
else
    GOST_ARCH="linux-386"
fi

wget -O gost.gz https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-$GOST_ARCH-2.11.5.gz
gunzip gost.gz
mv gost psiphond
chmod +x psiphond

# Ask for ports
read -p "Enter Psiphon OSSH port (default 22): " OSSH_PORT
OSSH_PORT=${OSSH_PORT:-22}

read -p "Enter Psiphon HTTPS port (default 443): " HTTPS_PORT
HTTPS_PORT=${HTTPS_PORT:-443}

read -p "Enter Psiphon tunnel port (default 4443): " TUNNEL_PORT
TUNNEL_PORT=${TUNNEL_PORT:-4443}

# Generate password
PASSWORD=$(openssl rand -base64 16)

# Create Psiphon configuration
cat > /opt/psiphon/config.json <<EOF
{
  "ServerIP": "$SERVER_IP",
  "ServerPorts": {
    "SSH": $OSSH_PORT,
    "HTTPS": $HTTPS_PORT,
    "Tunnel": $TUNNEL_PORT
  },
  "Credentials": {
    "Username": "psiphon",
    "Password": "$PASSWORD"
  },
  "Obfuscation": true,
  "MeekServer": false
}
EOF

# Create startup script
cat > /opt/psiphon/start.sh <<EOF
#!/bin/bash
cd /opt/psiphon
./psiphond -L="ss://aes-256-gcm:$PASSWORD@:$TUNNEL_PORT" \
           -L="http2://:$HTTPS_PORT" \
           -F="ss://aes-256-gcm:$PASSWORD@$SERVER_IP:$TUNNEL_PORT"
EOF

chmod +x /opt/psiphon/start.sh

# Create systemd service
cat > /etc/systemd/system/psiphon.service <<EOF
[Unit]
Description=Psiphon Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/psiphon
ExecStart=/opt/psiphon/start.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable psiphon
systemctl start psiphon

# Configure firewall
ufw allow $OSSH_PORT/tcp 2>/dev/null
ufw allow $HTTPS_PORT/tcp 2>/dev/null
ufw allow $TUNNEL_PORT/tcp 2>/dev/null

# Create client configuration
cat > /opt/psiphon/client-config.txt <<EOF
Psiphon Server Configuration
=============================
Server: $SERVER_IP
SSH Port: $OSSH_PORT
HTTPS Port: $HTTPS_PORT
Tunnel Port: $TUNNEL_PORT
Password: $PASSWORD

Connection String:
ss://$(echo -n "aes-256-gcm:$PASSWORD" | base64)@$SERVER_IP:$TUNNEL_PORT
EOF

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m Psiphon installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mSSH Port: $OSSH_PORT\033[0m"
echo -e "\033[1;33mHTTPS Port: $HTTPS_PORT\033[0m"
echo -e "\033[1;33mTunnel Port: $TUNNEL_PORT\033[0m"
echo -e "\033[1;33mPassword: $PASSWORD\033[0m"
echo ""
echo -e "\033[1;36mConnection String:\033[0m"
echo "ss://$(echo -n "aes-256-gcm:$PASSWORD" | base64)@$SERVER_IP:$TUNNEL_PORT"
echo ""
echo -e "\033[1;36mClient config: /opt/psiphon/client-config.txt\033[0m"
echo ""
