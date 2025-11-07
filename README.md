<div align="center">

# 🚀 Stream Monitor

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A Python tool for monitoring Kick streams and detecting chat mentions with Discord notifications**

*Stay updated on Kick streams with real-time chat monitoring and instant Discord alerts*

[Installation](#-installation) •
[Setup](#-setup) •
[Usage](#-usage) •
[Features](#-features) •
[Configuration](#-configuration) •
[License](#-license)

</div>

---

## 📖 Overview

Stream Monitor is a Python application that monitors Kick streaming channels in real-time, detecting mentions of your username and sending instant notifications to Discord. It uses WebSocket connections to Pusher for live chat monitoring and integrates with Discord webhooks for notifications.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎥 **Kick Integration** | Real-time monitoring of Kick chat rooms |
| 🔔 **Mention Detection** | Instant alerts when your username is mentioned |
| 📢 **Discord Notifications** | Webhook-based notifications to Discord channels |
| 🎨 **Emote Support** | Resolves emote URLs from 7TV and Kick |
| 🔄 **WebSocket Streaming** | Live chat monitoring via Pusher WebSocket |
| ⚙️ **Configurable** | Easy configuration via config.py |
| 🐳 **Docker Ready** | Containerized deployment support |

## 📦 Installation

### Using uv (Recommended)
```bash
git clone https://github.com/CodingInCarhartts/stream-monitor
cd stream-monitor
uv sync
```

### Using pip
```bash
git clone https://github.com/CodingInCarhartts/stream-monitor
cd stream-monitor
pip install -e .
```

### Docker
```bash
docker build -t stream-monitor .
docker run stream-monitor
```

## 🔧 Setup

### Prerequisites
- Python 3.13+
- Kick account
- Discord server with webhook

### Configuration
1. Copy the configuration template:
   ```bash
   cp config.py.example config.py
   ```

2. Edit `config.py` with your settings:
   ```python
   # Your Kick username
   KICK_USERNAME = "your_username"

   # Channels to monitor
   KICK_CHANNELS_TO_MONITOR = ["channel1", "channel2"]

   # Pusher configuration (usually doesn't need changes)
   PUSHER_APP_KEY = "your_pusher_key"
   PUSHER_CLUSTER = "us2"

   # Discord webhook URL
   DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/.../..."

   # User agent for requests
   KICK_USER_AGENT = "Mozilla/5.0..."
   ```

### Discord Webhook Setup
1. Go to your Discord server settings
2. Navigate to Integrations > Webhooks
3. Create a new webhook
4. Copy the webhook URL to your config

## 🚀 Usage

### Basic Usage
```bash
python app.py
```

### Output
The application will:
- Display chatroom IDs for monitored channels
- Start monitoring chat in real-time
- Send Discord notifications when mentions are detected

### Example Output
```
var chatroomIDs = map[string]string{
    "channel1": "123456",
    "channel2": "789012",
}
Starting Kick chat monitor...
Press Ctrl+C to stop

[MENTION] @your_username was mentioned in channel1
[Discord] Notification sent successfully
```

## 📝 Configuration

### config.py Options

| Option | Type | Description |
|--------|------|-------------|
| `KICK_USERNAME` | string | Your Kick username to monitor for mentions |
| `KICK_CHANNELS_TO_MONITOR` | list | List of Kick channels to monitor |
| `PUSHER_APP_KEY` | string | Pusher app key for WebSocket connection |
| `PUSHER_CLUSTER` | string | Pusher cluster (usually "us2") |
| `DISCORD_WEBHOOK_URL` | string | Discord webhook URL for notifications |
| `KICK_USER_AGENT` | string | User agent string for HTTP requests |
| `FALLBACK_CHATROOM_IDS` | dict | Fallback chatroom IDs if API fails |

### Environment Variables
You can override config values with environment variables:
- `KICK_USERNAME`
- `DISCORD_WEBHOOK_URL`

## 🛠️ Development

### Available Scripts
- `uv sync` - Install dependencies
- `uv run python app.py` - Run the application
- `uv run black .` - Format code

### Code Structure
```
stream-monitor/
├── app.py                 # Main application entry point
├── kick_monitor.py        # Kick chat monitoring logic
├── discord_notifier.py    # Discord webhook notifications
├── config.py              # Configuration settings
└── pyproject.toml         # Project configuration
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📜 License

[MIT License](LICENSE) - See LICENSE file for details.

---

<div align="center">
  <p>Built with ❤️ for the streaming community</p>
</div>