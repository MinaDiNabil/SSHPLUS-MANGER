#!/bin/bash
# SSL Tunnel (Stunnel) Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m    SSL Tunnel Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if Stunnel is installed
if [[ -e /etc/stunnel/stunnel.conf ]]; then
    echo -e "\033[1;33mSSL Tunnel is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Restart service"
    echo -e "[2] Show configuration"
    echo -e "[3] Add new tunnel"
    echo -e "[4] Uninstall SSL Tunnel"
    echo -e "[5] Exit"
    read -p "Select option: " option
    case $option in
        1)
            systemctl restart stunnel4
            echo -e "\033[1;32mSSL Tunnel restarted!\033[0m"
            exit 0
            ;;
        2)
            echo -e "\033[1;36m\nSSL Tunnel Configuration:\033[0m"
            cat /etc/stunnel/stunnel.conf
            exit 0
            ;;
        4)
            echo -e "\033[1;31mUninstalling SSL Tunnel...\033[0m"
            systemctl stop stunnel4
            systemctl disable stunnel4
            apt-get remove --purge -y stunnel4
            rm -rf /etc/stunnel
            echo -e "\033[1;32mSSL Tunnel uninstalled!\033[0m"
            exit 0
            ;;
        5)
            exit 0
            ;;
    esac
fi

# Install Stunnel
echo -e "\033[1;36mInstalling Stunnel...\033[0m"
apt-get update -y
apt-get install -y stunnel4

# Enable stunnel
sed -i 's/ENABLED=0/ENABLED=1/g' /etc/default/stunnel4

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for ports
read -p "Enter SSL port (default 443): " SSL_PORT
SSL_PORT=${SSL_PORT:-443}

read -p "Enter Dropbear port to forward (default 22): " DROP_PORT
DROP_PORT=${DROP_PORT:-22}

read -p "Enter OpenSSH port to forward (default 109): " OPENSSH_PORT
OPENSSH_PORT=${OPENSSH_PORT:-109}

# Generate SSL certificate
echo -e "\033[1;36mGenerating SSL certificate...\033[0m"
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
    -subj "/C=US/ST=None/L=None/O=None/CN=$SERVER_IP" \
    -keyout /etc/stunnel/stunnel.pem \
    -out /etc/stunnel/stunnel.pem 2>/dev/null

chmod 600 /etc/stunnel/stunnel.pem

# Create stunnel configuration
cat > /etc/stunnel/stunnel.conf <<EOF
; Stunnel Configuration File
; SSL Tunnel Service

pid = /var/run/stunnel.pid
cert = /etc/stunnel/stunnel.pem

[dropbear]
accept = $SSL_PORT
connect = 127.0.0.1:$DROP_PORT

[openssh]
accept = 444
connect = 127.0.0.1:$OPENSSH_PORT

[openvpn]
accept = 587
connect = 127.0.0.1:1194
EOF

# Create startup script
cat > /etc/stunnel/start.sh <<'EOF'
#!/bin/bash
systemctl restart stunnel4
sleep 2
systemctl status stunnel4 --no-pager
EOF

chmod +x /etc/stunnel/start.sh

# Start service
systemctl enable stunnel4
systemctl restart stunnel4

# Configure firewall
ufw allow $SSL_PORT/tcp 2>/dev/null
ufw allow 444/tcp 2>/dev/null
ufw allow 587/tcp 2>/dev/null

# Create status check script
cat > /usr/local/bin/ssl-status <<'EOF'
#!/bin/bash
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m      SSL Tunnel Status\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
systemctl status stunnel4 --no-pager | head -10
echo ""
echo -e "\033[1;36mActive Connections:\033[0m"
netstat -tnp | grep stunnel
echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
EOF

chmod +x /usr/local/bin/ssl-status

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m SSL Tunnel installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mSSL Ports:\033[0m"
echo -e "  - Dropbear SSL: $SSL_PORT"
echo -e "  - OpenSSH SSL: 444"
echo -e "  - OpenVPN SSL: 587"
echo ""
echo -e "\033[1;36mCheck status: ssl-status\033[0m"
echo ""
