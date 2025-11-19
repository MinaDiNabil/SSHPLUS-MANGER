# SSHPLUS MANAGER v2.0
### Advanced Multi-Protocol VPN Manager
#### By @MinaProNet

[![Version](https://img.shields.io/badge/version-2.0-blue.svg)](https://github.com/MinaDiNabil/SSHPLUS-MANGER)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Supported OS](https://img.shields.io/badge/OS-Ubuntu%20%7C%20Debian-orange.svg)](https://github.com/MinaDiNabil/SSHPLUS-MANGER)

## 📖 Description

SSHPLUS Manager is a comprehensive VPN and proxy management system that supports multiple protocols including OpenVPN, WireGuard, V2Ray, Shadowsocks, Hysteria (v1 & v2), WebSocket, SSL Tunnel, SlowDNS, and Psiphon.

Perfect for VPS administrators who need a unified interface to manage multiple tunneling protocols.

## ✨ Features

### VPN Protocols
- **OpenVPN**: Industry-standard VPN with full certificate management
- **WireGuard**: Modern, fast, and lightweight VPN
- **V2Ray**: Advanced proxy supporting VMess, VLESS, and Trojan protocols

### Proxy Protocols
- **Shadowsocks**: SOCKS5 proxy for bypassing censorship
- **Hysteria v1**: QUIC-based protocol for lossy networks
- **Hysteria v2**: Latest version with improved performance
- **Trojan-Go**: Stealth proxy mimicking HTTPS traffic

### Tunnel Protocols
- **WebSocket**: WebSocket-based tunnel for SSH/VPN
- **SSL Tunnel (Stunnel)**: SSL/TLS encryption layer
- **SlowDNS**: DNS tunneling for restricted networks
- **Psiphon**: Multi-protocol tunnel with obfuscation

### Management Features
- Centralized protocol manager (`protocolmanager`)
- Real-time status monitoring
- Easy installation and configuration
- User management system
- Bot integration for Telegram
- System optimization tools

## 🚀 Quick Installation

### For x86_64 Architecture:
```bash
apt update -y && apt upgrade -y && wget https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/master/Plus && chmod 777 Plus && ./Plus
```

### For ARM Architecture (aarch64):
```bash
apt update -y && apt upgrade -y && wget https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/master/Plus && chmod 777 Plus && ./Plus
```
*Select option [2] for ARM architecture during installation*

### Access Root (Optional):
```bash
wget https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/master/senharoot.sh && chmod 777 senharoot.sh && ./senharoot.sh
```

## 📋 Main Commands

After installation, use these commands:

- **`menu`** - Main management menu
- **`protocolmanager`** - Advanced protocol manager (NEW!)
- **`v2raymanager`** - V2Ray management interface
- **`ssl-status`** - Check SSL tunnel status
- **`slowdns-info`** - View SlowDNS information
- **`hysteria2-info`** - View Hysteria 2 details

## 🔧 Protocol Installation

During the main installation, you'll be prompted to install additional protocols. You can also install them later using:

```bash
protocolmanager
```

### Individual Protocol Installation:

```bash
# OpenVPN
bash /root/SSHPLUS-MANGER/Install/openvpn-install.sh

# WireGuard
bash /root/SSHPLUS-MANGER/Install/wireguard-install.sh

# Shadowsocks
bash /root/SSHPLUS-MANGER/Install/shadowsocks-install.sh

# Hysteria v1
bash /root/SSHPLUS-MANGER/Install/hysteria1-install.sh

# Hysteria v2
bash /root/SSHPLUS-MANGER/Install/hysteria2-install.sh

# V2Ray
bash /root/SSHPLUS-MANGER/Install/v2ray-install.sh

# WebSocket
bash /root/SSHPLUS-MANGER/Install/websocket-install.sh

# SSL Tunnel
bash /root/SSHPLUS-MANGER/Install/ssltunnel-install.sh

# SlowDNS
bash /root/SSHPLUS-MANGER/Install/slowdns-install.sh

# Psiphon
bash /root/SSHPLUS-MANGER/Install/psiphon-install.sh
```

## 📊 Protocol Comparison

| Protocol | Speed | Security | Compatibility | Best Use Case |
|----------|-------|----------|---------------|---------------|
| OpenVPN | Good | Excellent | Universal | General purpose, stable connections |
| WireGuard | Excellent | Excellent | Modern | Mobile devices, performance |
| V2Ray | Good | Excellent | Good | Advanced features, multi-protocol |
| Shadowsocks | Very Good | Good | Good | Bypassing censorship |
| Hysteria v1 | Excellent | Excellent | Modern | Lossy networks, high latency |
| Hysteria v2 | Excellent | Excellent | Modern | Latest features, best performance |
| Trojan-Go | Very Good | Excellent | Good | Stealth mode, HTTPS camouflage |
| WebSocket | Good | Good | Excellent | Web-based tunneling |
| SSL Tunnel | Good | Excellent | Good | SSL/TLS encryption layer |
| SlowDNS | Moderate | Good | Universal | Restricted networks, DNS-based |
| Psiphon | Good | Good | Good | Multi-protocol obfuscation |

## 🌐 Default Ports

- **OpenVPN**: 1194 (UDP)
- **WireGuard**: 51820 (UDP)
- **Shadowsocks**: 8388 (TCP/UDP)
- **Hysteria v1**: 36712 (UDP/TCP)
- **Hysteria v2**: 443 (UDP)
- **V2Ray**: 10085 (TCP), 10086 (WebSocket)
- **Trojan-Go**: 443 (TCP)
- **WebSocket**: 80 (TCP)
- **SSL Tunnel**: 443, 444, 587 (TCP)
- **SlowDNS**: 53 (UDP/TCP)
- **Psiphon**: 4443 (TCP)

## 📦 Requirements

- **OS**: Ubuntu 18.04+ or Debian 9+
- **RAM**: Minimum 512MB (1GB+ recommended)
- **Storage**: 10GB available space
- **Access**: Root privileges required
- **Network**: Open ports for protocols

## 🔐 Security Features

- Strong encryption for all protocols
- Automatic certificate generation
- Random password/key generation
- Firewall rules auto-configuration
- IP forwarding management
- Isolated protocol environments

## 📱 Telegram Bot Integration

SSHPLUS Manager includes Telegram bot integration for remote management:
- User creation and management
- Connection monitoring
- Server status checks
- Automated notifications

Configure the bot using the `bot` command after installation.

## 🆕 What's New in v2.0

- ✅ Added 10+ new protocols
- ✅ Advanced Protocol Manager
- ✅ Hysteria v2 support
- ✅ WebSocket tunneling
- ✅ SSL Tunnel integration
- ✅ SlowDNS implementation
- ✅ Psiphon support
- ✅ Improved V2Ray installer
- ✅ Enhanced user interface
- ✅ Real-time status monitoring
- ✅ Batch protocol installation

## 📞 Support & Contact

- **Developer**: @MinaProNet
- **Telegram Channel**: @SSHPLUS
- **GitHub**: https://github.com/MinaDiNabil/SSHPLUS-MANGER
- **Issues**: https://github.com/MinaDiNabil/SSHPLUS-MANGER/issues

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This tool is for educational and authorized testing purposes only. Users are responsible for complying with their local laws and regulations. The developers assume no liability for misuse.

## 🌟 Star History

If you find this project useful, please consider giving it a star! ⭐

---

**Made with ❤️ by @MinaProNet**

**Original concept inspired by @kiritosshxd**
