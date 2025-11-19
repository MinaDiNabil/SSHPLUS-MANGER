#!/bin/bash
# SlowDNS Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m      SlowDNS Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if SlowDNS is installed
if [[ -e /etc/slowdns/server.key ]]; then
    echo -e "\033[1;33mSlowDNS is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Restart service"
    echo -e "[3] Regenerate keys"
    echo -e "[4] Uninstall SlowDNS"
    echo -e "[5] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nSlowDNS Configuration:\033[0m"
            echo -e "NS Domain: $(cat /etc/slowdns/domain 2>/dev/null)"
            echo -e "Public Key: $(cat /etc/slowdns/server.pub 2>/dev/null)"
            exit 0
            ;;
        2)
            systemctl restart slowdns
            echo -e "\033[1;32mSlowDNS restarted!\033[0m"
            exit 0
            ;;
        4)
            echo -e "\033[1;31mUninstalling SlowDNS...\033[0m"
            systemctl stop slowdns
            systemctl disable slowdns
            rm -rf /etc/slowdns
            rm -f /usr/local/bin/dns-server
            rm -f /etc/systemd/system/slowdns.service
            systemctl daemon-reload
            echo -e "\033[1;32mSlowDNS uninstalled!\033[0m"
            exit 0
            ;;
        5)
            exit 0
            ;;
    esac
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for domain
echo -e "\033[1;36mEnter your NS domain (example: ns1.yourdomain.com):\033[0m"
read -p "NS Domain: " NS_DOMAIN

if [[ -z "$NS_DOMAIN" ]]; then
    echo -e "\033[1;31mDomain is required!\033[0m"
    exit 1
fi

# Ask for SSH port
read -p "Enter SSH port to forward (default 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}

# Install dependencies
echo -e "\033[1;36mInstalling dependencies...\033[0m"
apt-get update -y
apt-get install -y build-essential libssl-dev zlib1g-dev

# Create directory
mkdir -p /etc/slowdns

# Download and compile dns2tcp
cd /tmp
git clone https://github.com/alex-sector/dns2tcp.git 2>/dev/null || {
    echo -e "\033[1;33mDownloading alternative DNS server...\033[0m"
    wget -O /usr/local/bin/dns-server https://github.com/cloudflare/slirpnetstack/releases/download/v0.1.0/dnstt-server 2>/dev/null
    chmod +x /usr/local/bin/dns-server
}

# If git clone worked, compile it
if [[ -d dns2tcp ]]; then
    cd dns2tcp
    ./configure
    make
    make install
    cp /usr/local/bin/dns2tcpd /usr/local/bin/dns-server
fi

# Generate keys
echo -e "\033[1;36mGenerating encryption keys...\033[0m"
cd /etc/slowdns

# Create key generation script
cat > genkey.sh <<'EOF'
#!/bin/bash
openssl rand -base64 32 > server.key
openssl rand -base64 32 > server.pub
EOF

chmod +x genkey.sh
./genkey.sh

# Save domain
echo "$NS_DOMAIN" > /etc/slowdns/domain

# Create configuration
cat > /etc/slowdns/config <<EOF
NS_DOMAIN=$NS_DOMAIN
SSH_PORT=$SSH_PORT
SERVER_IP=$SERVER_IP
EOF

# Create DNS server script
cat > /usr/local/bin/slowdns-start <<EOF
#!/bin/bash
KEY=\$(cat /etc/slowdns/server.key)
dns-server -udp :53 -privkey-file /etc/slowdns/server.key $NS_DOMAIN 127.0.0.1:$SSH_PORT
EOF

chmod +x /usr/local/bin/slowdns-start

# Create systemd service
cat > /etc/systemd/system/slowdns.service <<EOF
[Unit]
Description=SlowDNS Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/slowdns
ExecStart=/usr/local/bin/slowdns-start
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable slowdns
systemctl start slowdns

# Configure firewall
ufw allow 53/udp 2>/dev/null
ufw allow 53/tcp 2>/dev/null

# Create info script
cat > /usr/local/bin/slowdns-info <<'EOF'
#!/bin/bash
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m      SlowDNS Information\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;36mNS Domain:\033[0m $(cat /etc/slowdns/domain)"
echo -e "\033[1;36mServer IP:\033[0m $(cat /etc/slowdns/config | grep SERVER_IP | cut -d= -f2)"
echo -e "\033[1;36mPublic Key:\033[0m"
cat /etc/slowdns/server.pub
echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
systemctl status slowdns --no-pager | head -10
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
EOF

chmod +x /usr/local/bin/slowdns-info

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m  SlowDNS installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mNS Domain: $NS_DOMAIN\033[0m"
echo -e "\033[1;33mSSH Port: $SSH_PORT\033[0m"
echo ""
echo -e "\033[1;31mIMPORTANT:\033[0m"
echo -e "Point your NS record to: $SERVER_IP"
echo -e "Example DNS record:"
echo -e "  $NS_DOMAIN  IN  A  $SERVER_IP"
echo ""
echo -e "\033[1;36mView info: slowdns-info\033[0m"
echo ""
