# CHANGELOG - SSHPLUS Manager

## Version 2.0.0 - Protocol Enhancement Update

### ✨ New Features

#### 1. Protocol Manager (`protocolmanager`)
- Centralized management interface for all VPN/Proxy protocols
- Real-time status monitoring for all installed protocols
- Quick install/uninstall/restart capabilities
- Color-coded status indicators

#### 2. New Protocol Support

##### OpenVPN
- Full OpenVPN server installation
- Easy-RSA integration for certificate management
- Client configuration generation
- Port: 1194 UDP (default)
- Network: 10.8.0.0/24
- Features:
  - AES-256-CBC encryption
  - SHA256 authentication
  - TLS-auth for additional security
  - DNS push (8.8.8.8, 8.8.4.4)

##### WireGuard
- Modern, fast, and secure VPN protocol
- Automatic key generation
- QR code support for mobile clients
- Port: 51820 UDP (default)
- Network: 10.66.66.0/24
- Features:
  - ChaCha20 encryption
  - Simple configuration
  - Low overhead
  - Perfect for mobile devices

##### Shadowsocks
- Advanced proxy protocol for bypassing restrictions
- Shadowsocks-libev implementation
- Random password generation
- Port: 8388 (default, configurable)
- Features:
  - AEAD ciphers (aes-256-gcm)
  - Fast-open support
  - TCP and UDP support
  - Base64 connection string generation

##### Hysteria
- Next-generation protocol optimized for lossy networks
- Built on QUIC protocol
- Self-signed certificate generation
- Port: 36712 UDP/TCP (default)
- Features:
  - 100/100 Mbps bandwidth configuration
  - Password authentication
  - GeoIP/GeoSite blocking support
  - Obfuscation support

### 🔧 Improvements

#### Enhanced Installation Script
- Interactive protocol installation during setup
- Options to install individual protocols or all at once
- Skip option to install protocols later
- Automatic protocol manager installation

#### Protocol Management
- Unified management interface
- Service status monitoring
- Log viewing capabilities
- Restart/Stop/Start controls
- Batch installation support

### 📝 Usage

#### Install Protocols During Setup
When running the main installer:
```bash
./Plus
```
After base installation, you'll be prompted to install protocols.

#### Install Protocols After Setup
Use the protocol manager:
```bash
protocolmanager
```

#### Individual Protocol Installation
```bash
# OpenVPN
bash /root/SSHPLUS-MANGER/Install/openvpn-install.sh

# WireGuard
bash /root/SSHPLUS-MANGER/Install/wireguard-install.sh

# Shadowsocks
bash /root/SSHPLUS-MANGER/Install/shadowsocks-install.sh

# Hysteria
bash /root/SSHPLUS-MANGER/Install/hysteria-install.sh
```

### 🎯 Protocol Comparison

| Protocol | Speed | Security | Compatibility | Use Case |
|----------|-------|----------|---------------|----------|
| OpenVPN | Good | Excellent | Universal | General purpose, stable |
| WireGuard | Excellent | Excellent | Modern | Mobile, performance |
| Shadowsocks | Very Good | Good | Good | Bypassing restrictions |
| Hysteria | Excellent | Excellent | Modern | Lossy networks, gaming |
| V2Ray | Good | Excellent | Good | Advanced features |
| Trojan-Go | Very Good | Excellent | Good | Stealth mode |

### 📦 File Structure

```
SSHPLUS-MANGER/
├── Plus (Updated main installer)
├── Install/
│   ├── openvpn-install.sh (New)
│   ├── wireguard-install.sh (New)
│   ├── shadowsocks-install.sh (New)
│   └── hysteria-install.sh (New)
├── Modulos/
│   └── protocolmanager (New)
└── CHANGELOG.md (This file)
```

### 🔐 Security Notes

- All protocols use strong encryption by default
- Random password/key generation for enhanced security
- Firewall rules automatically configured
- IP forwarding enabled where required
- Each protocol runs on separate ports

### 🌟 Existing Features

The following features from previous versions remain:
- V2Ray Manager
- Trojan-Go support
- SlowDNS
- SSH user management
- Bot integration
- System optimization tools

### 📞 Support

For more information and support:
- Telegram: @SSHPLUS
- GitHub: kiritosshxd/SSHPLUS

### ⚠️ Requirements

- Ubuntu 18.04+ or Debian 9+
- Root access
- Minimum 512MB RAM
- 10GB available storage
- Open ports for protocols

### 🚀 Future Plans

- Xray support
- NaiveProxy integration
- Multi-port support for protocols
- Advanced QoS features
- Automated backup/restore for protocol configs
