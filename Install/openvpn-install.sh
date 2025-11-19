#!/bin/bash
# OpenVPN Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m     OpenVPN Installation Script\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if OpenVPN is already installed
if [[ -e /etc/openvpn/server.conf ]]; then
    echo -e "\033[1;33mOpenVPN is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Add new user"
    echo -e "[2] Remove user"
    echo -e "[3] Uninstall OpenVPN"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        3)
            echo -e "\033[1;31mUninstalling OpenVPN...\033[0m"
            systemctl stop openvpn@server
            systemctl disable openvpn@server
            apt-get remove --purge -y openvpn
            rm -rf /etc/openvpn
            echo -e "\033[1;32mOpenVPN uninstalled successfully!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Install OpenVPN
echo -e "\033[1;36mInstalling OpenVPN...\033[0m"
apt-get update -y
apt-get install -y openvpn easy-rsa iptables-persistent

# Setup Easy-RSA
echo -e "\033[1;36mConfiguring Easy-RSA...\033[0m"
make-cadir /etc/openvpn/easy-rsa
cd /etc/openvpn/easy-rsa

# Initialize PKI
./easyrsa init-pki
./easyrsa build-ca nopass <<EOF
SSHPlus-CA
EOF

# Generate server certificate
./easyrsa gen-req server nopass <<EOF

EOF
./easyrsa sign-req server server <<EOF
yes
EOF

# Generate DH parameters
./easyrsa gen-dh

# Generate TLS auth key
openvpn --genkey --secret /etc/openvpn/ta.key

# Copy certificates to OpenVPN directory
cp pki/ca.crt /etc/openvpn/
cp pki/issued/server.crt /etc/openvpn/
cp pki/private/server.key /etc/openvpn/
cp pki/dh.pem /etc/openvpn/

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Create server.conf
cat > /etc/openvpn/server.conf <<EOF
port 1194
proto udp
dev tun
ca ca.crt
cert server.crt
key server.key
dh dh.pem
tls-auth ta.key 0
server 10.8.0.0 255.255.255.0
ifconfig-pool-persist ipp.txt
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 8.8.8.8"
push "dhcp-option DNS 8.8.4.4"
keepalive 10 120
cipher AES-256-CBC
auth SHA256
user nobody
group nogroup
persist-key
persist-tun
status openvpn-status.log
verb 3
EOF

# Enable IP forwarding
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Configure iptables
NIC=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o $NIC -j MASQUERADE
iptables-save > /etc/iptables/rules.v4

# Start OpenVPN
systemctl start openvpn@server
systemctl enable openvpn@server

# Create client configuration template
mkdir -p /etc/openvpn/clients

cat > /etc/openvpn/client-template.txt <<EOF
client
dev tun
proto udp
remote $SERVER_IP 1194
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-CBC
auth SHA256
verb 3
EOF

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m  OpenVPN installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mPort: 1194 UDP\033[0m"
echo -e "\033[1;33mNetwork: 10.8.0.0/24\033[0m"
echo ""
