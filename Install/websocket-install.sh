#!/bin/bash
# WebSocket Proxy Auto Installer for SSHPLUS Manager
# Version: 1.0

clear
[[ "$(whoami)" != "root" ]] && {
    echo -e "\033[1;31mError: You need to run as root\033[0m"
    exit 1
}

echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33m   WebSocket Proxy Installation\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo ""

# Check if WebSocket is installed
if [[ -e /etc/systemd/system/ws-stunnel.service ]]; then
    echo -e "\033[1;33mWebSocket is already installed!\033[0m"
    echo -e "\033[1;36mWhat do you want to do?\033[0m"
    echo -e "[1] Restart service"
    echo -e "[2] Show configuration"
    echo -e "[3] Uninstall WebSocket"
    echo -e "[4] Exit"
    read -p "Select option: " option
    case $option in
        1)
            systemctl restart ws-stunnel
            echo -e "\033[1;32mWebSocket restarted!\033[0m"
            exit 0
            ;;
        2)
            echo -e "\033[1;36m\nWebSocket Configuration:\033[0m"
            cat /etc/websocket/config.py 2>/dev/null || echo "Config not found"
            exit 0
            ;;
        3)
            echo -e "\033[1;31mUninstalling WebSocket...\033[0m"
            systemctl stop ws-stunnel
            systemctl disable ws-stunnel
            rm -rf /etc/websocket
            rm -f /etc/systemd/system/ws-stunnel.service
            systemctl daemon-reload
            echo -e "\033[1;32mWebSocket uninstalled!\033[0m"
            exit 0
            ;;
        4)
            exit 0
            ;;
    esac
fi

# Install Python and dependencies
echo -e "\033[1;36mInstalling dependencies...\033[0m"
apt-get update -y
apt-get install -y python3 python3-pip python3-dev

# Create directory
mkdir -p /etc/websocket

# Install websocket libraries
pip3 install websockets asyncio

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

# Ask for ports
read -p "Enter WebSocket port (default 80): " WS_PORT
WS_PORT=${WS_PORT:-80}

read -p "Enter SSL WebSocket port (default 443): " WSS_PORT
WSS_PORT=${WSS_PORT:-443}

read -p "Enter SSH port to forward (default 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}

# Create WebSocket proxy script
cat > /etc/websocket/ws-proxy.py <<'WSEOF'
#!/usr/bin/env python3
import asyncio
import websockets
import socket
import sys

# Configuration
SSH_HOST = '127.0.0.1'
SSH_PORT = 22
WS_PORT = 80

async def forward(websocket, reader, writer):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            await websocket.send(data)
    except Exception as e:
        pass
    finally:
        writer.close()

async def reverse(websocket, reader, writer):
    try:
        async for message in websocket:
            writer.write(message)
            await writer.drain()
    except Exception as e:
        pass

async def handle_client(websocket, path):
    try:
        reader, writer = await asyncio.open_connection(SSH_HOST, SSH_PORT)

        forward_task = asyncio.create_task(forward(websocket, reader, writer))
        reverse_task = asyncio.create_task(reverse(websocket, reader, writer))

        await asyncio.gather(forward_task, reverse_task)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", WS_PORT)
    print(f"WebSocket proxy running on port {WS_PORT}")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
WSEOF

# Update configuration in script
sed -i "s/SSH_PORT = 22/SSH_PORT = $SSH_PORT/" /etc/websocket/ws-proxy.py
sed -i "s/WS_PORT = 80/WS_PORT = $WS_PORT/" /etc/websocket/ws-proxy.py

chmod +x /etc/websocket/ws-proxy.py

# Create systemd service
cat > /etc/systemd/system/ws-stunnel.service <<EOF
[Unit]
Description=WebSocket Proxy Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/websocket
ExecStart=/usr/bin/python3 /etc/websocket/ws-proxy.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable ws-stunnel
systemctl start ws-stunnel

# Configure firewall
ufw allow $WS_PORT/tcp 2>/dev/null
ufw allow $WSS_PORT/tcp 2>/dev/null

echo ""
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;32m WebSocket installed successfully!\033[0m"
echo -e "\033[1;32m════════════════════════════════════════\033[0m"
echo -e "\033[1;33mServer IP: $SERVER_IP\033[0m"
echo -e "\033[1;33mWebSocket Port: $WS_PORT\033[0m"
echo -e "\033[1;33mSSH Forward Port: $SSH_PORT\033[0m"
echo ""
echo -e "\033[1;36mWebSocket URL: ws://$SERVER_IP:$WS_PORT\033[0m"
echo ""
