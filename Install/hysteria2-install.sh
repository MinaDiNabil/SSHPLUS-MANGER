#!/bin/bash
# Hysteria 2 Auto Installer for SSHPLUS Manager
# Version: 2.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m    Hysteria 2 Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if Hysteria2 is installed
if [[ -e /etc/hysteria2/config.yaml ]]; then
    echo -e "\033[1;33mHysteria 2 is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Restart service"
    echo -e "[3] Uninstall Hysteria 2"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nHysteria 2 Configuration:\033[0m"
            cat /etc/hysteria2/config.yaml
            exit 0
            ;;
        2)
            systemctl restart hysteria2-server
            echo -e "\033[1;32mHysteria 2 restarted!\033[0m"
            exit 0
            ;;
        3)
            echo -e "\033[1;31mUninstalling Hysteria 2...\033[0m"
            systemctl stop hysteria2-server
            systemctl disable hysteria2-server
            rm -rf /etc/hysteria2
            rm -f /usr/local/bin/hysteria2
            echo -e "\033[1;32mHysteria 2 uninstalled!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for port
read -p "Enter port (default 443): " PORT
PORT=${PORT:-443}

# Generate password
PASSWORD=$(openssl rand -base64 32)

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        HY_ARCH="amd64"
        ;;
    aarch64)
        HY_ARCH="arm64"
        ;;
    armv7l)
        HY_ARCH="armv7"
        ;;
    *)
        echo -e "\033[1;31mUnsupported architecture: $ARCH\033[0m"
        exit 1
        ;;
esac

# Download Hysteria 2
echo -e "\033[1;36mDownloading Hysteria 2...\033[0m"
wget -O /usr/local/bin/hysteria2 "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-$HY_ARCH"
chmod +x /usr/local/bin/hysteria2

# Create configuration directory
mkdir -p /etc/hysteria2

# Generate self-signed certificate
echo -e "\033[1;36mGenerating SSL certificate...\033[0m"
openssl req -x509 -nodes -newkey ec:<(openssl ecparam -name prime256v1) \
    -keyout /etc/hysteria2/server.key \
    -out /etc/hysteria2/server.crt \
    -days 365 \
    -subj "/CN=$SERVER_IP" 2>/dev/null

# Create Hysteria 2 configuration (YAML format)
cat > /etc/hysteria2/config.yaml <<EOF
listen: :$PORT

tls:
  cert: /etc/hysteria2/server.crt
  key: /etc/hysteria2/server.key

auth:
  type: password
  password: $PASSWORD

masquerade:
  type: proxy
  proxy:
    url: https://www.bing.com
    rewriteHost: true

bandwidth:
  up: 100 mbps
  down: 100 mbps

ignoreClientBandwidth: false

quic:
  initStreamReceiveWindow: 16777216
  maxStreamReceiveWindow: 16777216
  initConnReceiveWindow: 33554432
  maxConnReceiveWindow: 33554432
  maxIdleTimeout: 30s
  maxIncomingStreams: 1024
  disablePathMTUDiscovery: false

EOF

# Create systemd service
cat > /etc/systemd/system/hysteria2-server.service <<EOF
[Unit]
Description=Hysteria 2 Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/hysteria2
ExecStart=/usr/local/bin/hysteria2 server -c /etc/hysteria2/config.yaml
Restart=on-failure
RestartSec=5s
LimitNOFILE=infinity

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable hysteria2-server
systemctl start hysteria2-server

# Open firewall
ufw allow $PORT/udp 2>/dev/null

# Generate connection URI
CONNECTION_URI="hysteria2://$PASSWORD@$SERVER_IP:$PORT/?insecure=1&sni=$SERVER_IP"

# Create client configuration
cat > /etc/hysteria2/client.yaml <<EOF
server: $SERVER_IP:$PORT

auth: $PASSWORD

tls:
  sni: $SERVER_IP
  insecure: true

bandwidth:
  up: 100 mbps
  down: 100 mbps

socks5:
  listen: 127.0.0.1:1080

http:
  listen: 127.0.0.1:8080
EOF

# Create info script
cat > /usr/local/bin/hysteria2-info <<'HYINFO'
#!/bin/bash
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m      Hysteria 2 Information\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
cat /etc/hysteria2/config.yaml
echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
systemctl status hysteria2-server --no-pager | head -10
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
HYINFO

chmod +x /usr/local/bin/hysteria2-info

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m Hysteria 2 installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mPort: $PORT (UDP)\033[0m"
echo -e "\033[1;33mPassword: $PASSWORD\033[0m"
echo -e "\033[1;33mBandwidth: 100/100 Mbps\033[0m"
echo ""
echo -e "\033[1;36mConnection URI:\033[0m"
echo "$CONNECTION_URI"
echo ""
echo -e "\033[1;36mClient config: /etc/hysteria2/client.yaml\033[0m"
echo -e "\033[1;36mView info: hysteria2-info\033[0m"
echo ""
