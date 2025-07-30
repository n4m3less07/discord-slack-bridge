# Discord-Slack Bridge Bot

A bot that bridges messages between a **Discord server** and **Slack**, using **Redis** as a message queue or transport layer.

---

## 📦 Requirements

- Python 3.8+
- Redis server (local or remote)
- Slack Bot Token & Channel ID
- Discord Bot Token & Guild (Server) setup

---

## 🧰 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/n4m3less07/discord-slack-bridge
cd discord-slack-bridge
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**
Copy the example environment file and configure your tokens:
```bash
cp .env.example .env
```
Then edit `.env` with your actual values:

4. **Run the bridge:**
```bash
./start_bridge.sh
```
or
```bash
bash start_bridge.sh
```

---



## ⚙️ Features

* Listens to messages from Discord and publishes to Redis
* Slack bot subscribes to Redis and sends messages to a Slack channel
* Simple message synchronization bridge

---

## 🛠️ Tech Stack

* Discord.py
* Slack Bolt
* Redis
* python-dotenv

