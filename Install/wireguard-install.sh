#!/bin/bash
# WireGuard Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m    WireGuard Installation Script\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if WireGuard is installed
if [[ -e /etc/wireguard/wg0.conf ]]; then
    echo -e "\033[1;33mWireGuard is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Add new client"
    echo -e "[2] Remove client"
    echo -e "[3] Uninstall WireGuard"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        3)
            echo -e "\033[1;31mUninstalling WireGuard...\033[0m"
            systemctl stop wg-quick@wg0
            systemctl disable wg-quick@wg0
            apt-get remove --purge -y wireguard wireguard-tools
            rm -rf /etc/wireguard
            echo -e "\033[1;32mWireGuard uninstalled successfully!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Install WireGuard
echo -e "\033[1;36mInstalling WireGuard...\033[0m"
apt-get update -y
apt-get install -y wireguard wireguard-tools qrencode

# Create WireGuard directory
mkdir -p /etc/wireguard/clients
cd /etc/wireguard

# Generate server keys
wg genkey | tee server_private.key | wg pubkey > server_public.key
SERVER_PRIVATE_KEY=$(cat server_private.key)
SERVER_PUBLIC_KEY=$(cat server_public.key)

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Get network interface
NIC=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)

# Create server configuration
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIVATE_KEY
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o $NIC -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o $NIC -j MASQUERADE
SaveConfig = false
EOF

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Start WireGuard
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0

# Open firewall port
ufw allow 51820/udp 2>/dev/null

# Create client template
cat > /etc/wireguard/client-template.conf <<EOF
[Interface]
PrivateKey = CLIENT_PRIVATE_KEY
Address = CLIENT_IP/32
DNS = 8.8.8.8, 8.8.4.4

[Peer]
PublicKey = $SERVER_PUBLIC_KEY
Endpoint = $SERVER_IP:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m  WireGuard installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mPort: 51820 UDP\033[0m"
echo -e "\033[1;33mNetwork: 10.66.66.0/24\033[0m"
echo -e "\033[1;33mServer Public Key: $SERVER_PUBLIC_KEY\033[0m"
echo ""
echo -e "\033[1;36mTo add clients, use the WireGuard manager\033[0m"
echo ""
