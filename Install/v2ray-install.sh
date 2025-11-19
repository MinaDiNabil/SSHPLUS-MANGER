#!/bin/bash
# V2Ray Auto Installer for SSHPLUS Manager
# Version: 2.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m       V2Ray Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if V2Ray is installed
if [[ -e /usr/local/bin/v2ray ]]; then
    echo -e "\033[1;33mV2Ray is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Show configuration"
    echo -e "[2] Restart service"
    echo -e "[3] Add new user"
    echo -e "[4] Uninstall V2Ray"
    echo -e "[5] Exit"
    read -p "Select option: " option
    case $option in
        1)
            echo -e "\033[1;36m\nV2Ray Configuration:\033[0m"
            cat /usr/local/etc/v2ray/config.json
            exit 0
            ;;
        2)
            systemctl restart v2ray
            echo -e "\033[1;32mV2Ray restarted!\033[0m"
            exit 0
            ;;
        4)
            echo -e "\033[1;31mUninstalling V2Ray...\033[0m"
            systemctl stop v2ray
            systemctl disable v2ray
            bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh) --remove
            rm -rf /usr/local/etc/v2ray
            echo -e "\033[1;32mV2Ray uninstalled!\033[0m"
            exit 0
            ;;
        5)
            exit 0
            ;;
    esac
fi

# Install V2Ray
echo -e "\033[1;36mInstalling V2Ray...\033[0m"
bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh)

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for port
read -p "Enter V2Ray port (default 10085): " V2RAY_PORT
V2RAY_PORT=${V2RAY_PORT:-10085}

# Generate UUID
UUID=$(cat /proc/sys/kernel/random/uuid)

# Ask for protocol
echo ""
echo -e "\033[1;36mSelect protocol:\033[0m"
echo -e "[1] VMess"
echo -e "[2] VLESS"
echo -e "[3] Trojan"
read -p "Protocol: " PROTO_CHOICE

PROTOCOL="vmess"
case $PROTO_CHOICE in
    2) PROTOCOL="vless" ;;
    3) PROTOCOL="trojan" ;;
esac

# Create configuration directory
mkdir -p /usr/local/etc/v2ray

# Create V2Ray configuration based on protocol
if [[ "$PROTOCOL" == "vmess" ]]; then
cat > /usr/local/etc/v2ray/config.json <<EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": $V2RAY_PORT,
      "protocol": "vmess",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "alterId": 0
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "none"
      }
    },
    {
      "port": $(($V2RAY_PORT + 1)),
      "protocol": "vmess",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "alterId": 0
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {
          "path": "/v2ray"
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom"
    }
  ]
}
EOF

elif [[ "$PROTOCOL" == "vless" ]]; then
cat > /usr/local/etc/v2ray/config.json <<EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": $V2RAY_PORT,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "level": 0
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "none"
      }
    },
    {
      "port": $(($V2RAY_PORT + 1)),
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "level": 0
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {
          "path": "/vless"
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom"
    }
  ]
}
EOF

else
cat > /usr/local/etc/v2ray/config.json <<EOF
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": $V2RAY_PORT,
      "protocol": "trojan",
      "settings": {
        "clients": [
          {
            "password": "$UUID"
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "none"
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom"
    }
  ]
}
EOF
fi

# Start service
systemctl enable v2ray
systemctl start v2ray

# Configure firewall
ufw allow $V2RAY_PORT/tcp 2>/dev/null
ufw allow $(($V2RAY_PORT + 1))/tcp 2>/dev/null

# Generate connection links
if [[ "$PROTOCOL" == "vmess" ]]; then
    VMESS_LINK=$(echo -n "{\"v\":\"2\",\"ps\":\"SSHPLUS-VMess\",\"add\":\"$SERVER_IP\",\"port\":\"$V2RAY_PORT\",\"id\":\"$UUID\",\"aid\":\"0\",\"net\":\"tcp\",\"type\":\"none\",\"host\":\"\",\"path\":\"\",\"tls\":\"\"}" | base64 -w 0)
    VMESS_WS=$(echo -n "{\"v\":\"2\",\"ps\":\"SSHPLUS-VMess-WS\",\"add\":\"$SERVER_IP\",\"port\":\"$(($V2RAY_PORT + 1))\",\"id\":\"$UUID\",\"aid\":\"0\",\"net\":\"ws\",\"type\":\"none\",\"host\":\"\",\"path\":\"/v2ray\",\"tls\":\"\"}" | base64 -w 0)
fi

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m   V2Ray installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mProtocol: $PROTOCOL\033[0m"
echo -e "\033[1;33mPort: $V2RAY_PORT (TCP)\033[0m"
echo -e "\033[1;33mPort: $(($V2RAY_PORT + 1)) (WebSocket)\033[0m"
echo -e "\033[1;33mUUID/Password: $UUID\033[0m"
echo ""

if [[ "$PROTOCOL" == "vmess" ]]; then
    echo -e "\033[1;36mVMess Link (TCP):\033[0m"
    echo "vmess://$VMESS_LINK"
    echo ""
    echo -e "\033[1;36mVMess Link (WebSocket):\033[0m"
    echo "vmess://$VMESS_WS"
    echo ""
fi

echo -e "\033[1;36mConfiguration saved at: /usr/local/etc/v2ray/config.json\033[0m"
echo ""
