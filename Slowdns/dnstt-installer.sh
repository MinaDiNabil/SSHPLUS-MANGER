#!/bin/bash

BIN_NAME="dnstt-manager"
BIN_PATH="/usr/local/bin/$BIN_NAME"
BIN_URL="https://github.com/MinaDiNabil/SSHPLUS-MANGER/raw/refs/heads/main/Slowdns/$BIN_NAME"

clear

if [ -f "$BIN_PATH" ]; then
    echo "[!] $BIN_NAME is already installed. Removing to reinstall..."
    sudo rm -f "$BIN_PATH"
fi

echo "[+] Downloading $BIN_NAME..."
curl -sSL "$BIN_URL" -o "$BIN_NAME"

if [ ! -f "$BIN_NAME" ]; then
    echo "[ERROR] Failed to download binary."
    exit 1
fi

chmod +x "$BIN_NAME"
sudo mv "$BIN_NAME" "$BIN_PATH"

echo "[✔] Installation complete! You can run it with:"
echo "     dnstt-manager"
