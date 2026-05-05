# Gork — Discord AI Bot

A modular, config-driven Discord bot powered by the Hack Club AI proxy.
Gork responds when summoned, or when it detects you want to create something.

---

## 🛠️ Tech Stack

- **Language**: Python 3.8+
- **Framework**: [discord.py](https://github.com/Rapptz/discord.py)
- **AI Proxy**: [Hack Club AI](https://ai.hackclub.com/) (Supports Gemini, GPT-4, etc.)
- **Image Generation**: Hack Club AI (`google/gemini-2.5-flash-image`)
- **Package Manager**: `pip`

---

## ✨ Features

- **AI-Powered Responses**: Uses Hack Club AI proxy for intelligent, personality-driven replies.
- **Image Generation**: Generate images from text prompts with `/imagine` or natural language.
- **Intelligent Intent Detection**: Automatically detects image-generation requests in normal conversation.
- **Slash Commands**: Full suite of commands for management, blacklisting, whitelisting, and more.
- **Persistent State**: Blacklists, whitelists, user memories, and settings saved to disk.
- **Structured Logging**: Console and optional Discord channel logging with embeds.
- **Personality Customization**: Fully configurable bot personality and behavior via JSON.
- **Context Awareness**: Includes recent message history for coherent conversations.
- **DM Support**: Works in direct messages as well as servers.
- **User Memories**: Automatically extracts and stores user-specific information to personalize interactions.

---

## 📋 Requirements

- Python 3.8 or higher
- A Discord Bot Token (via [Discord Developer Portal](https://discord.com/developers/applications))
- A Hack Club AI API Key (via [Hack Club AI Dashboard](https://ai.hackclub.com/dashboard))

---

## 🚀 Quick Start

### 1. Clone the project

```bash
git clone <your-repo> gork
cd gork
```

### 2. Setup Environment

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications).
2. **New Application** → name it "Gork".
3. **Bot** tab → **Add Bot** → copy the **Token**.
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
   - **Server Members Intent** (optional, for better name resolution)
5. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Read Message History`, `View Channels`, `Embed Links`, `Attach Files`
6. Open the generated URL and invite Gork to your server.

### 4. Configure the Bot

1. Copy the example config:
   ```bash
   cp config/config.example.json config/config.json
   ```
2. Open `config/config.json` and fill in your tokens:
   - `discord_token`: Your Discord bot token.
   - `hackclub_api_key`: Your Hack Club AI key.
   - `sync_guild_id`: (Optional) Set to your server ID for instant command updates during dev.

### 5. Run the Bot

```bash
python bot.py
```

---

## 📂 Project Structure

```
gork/
├── bot.py              # Main entry point & Discord event handling
├── ai.py               # AI client (text responses & intent detection)
├── commands.py         # Slash command definitions & registration
├── image_gen.py        # Image generation client (Gemini-image)
├── config_loader.py    # Configuration management
├── state.py            # Persistent state management (JSON-based)
├── gork_logger.py      # Structured logging (Console + Discord)
├── utils.py            # Helper functions (message parsing, etc.)
├── requirements.txt    # Python dependencies
├── config/
│   ├── config.example.json   # Configuration template
│   └── config.json           # Active configuration (gitignored)
└── data/
    └── state.json            # Runtime persistent state (gitignored)
```

---

## 🎮 How to Trigger Gork

| Trigger | Example | Notes |
|---------|-------------|-------|
| **Direct Mention** | `@Gork what is recursion?` | Works in servers and DMs |
| **Reply** | *Replies to Gork's message* | Includes conversation context |
| **Direct Message** | `hey gork` | No @mention required in DMs |
| **Implicit Image Request** | `draw me a robot cat` | Auto-detects intent to generate images |

---

## ⌨️ Slash Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/imagine <prompt>` | Generate an AI image | Public |
| `/gork help` | Show help menu | Public |
| `/status set <text>` | Update bot status message | Manager |
| `/blacklist add <user/channel>` | Block interaction | Manager |
| `/blacklist remove <user/channel>` | Unblock interaction | Manager |
| `/blacklist list` | Show all blocks | Manager |
| `/whitelist on/off <channel>` | Toggle whitelist mode | Manager |
| `/memory remember <user> <key> <val>` | Save user fact | Manager |
| `/memory recall <user> <key>` | Get user fact | Manager |
| `/set_log_channel <channel>` | Set Discord log output | Manager |
| `/gork enable/disable` | Global bot toggle | Manager |

> **Note**: Manager commands require the role specified in `manager_role_name` (default: `gork-manager`).

---

## 🧠 Changing the Personality

Personality is 100% decoupled from code. Edit `config/config.json` to change Gork's soul:

| Field | Description |
|-------|-------------|
| `name` | Bot's name in prompts |
| `description` | Core backstory & identity |
| `tone` | Emotional register and voice |
| `temperature` | Randomness (0.0 to 1.0) |
| `style_rules` | List of formatting/writing rules |
| `behavioral_tendencies` | How Gork acts in different situations |
| `response_formatting` | Length, structure, markdown rules |

---

## ⚙️ Environment Variables

- `GORK_CONFIG`: Path to a custom config file (default: `config/config.json`).
  ```bash
  GORK_CONFIG=prod.json python bot.py
  ```

---

## 📄 License

- [ ] TODO: Add a LICENSE file (e.g., MIT).

---

## 🛠️ Troubleshooting

- **Commands not appearing?** Use `/gork help` to force a sync, or set `sync_guild_id` in config for instant updates in development.
- **Bot not responding?** Check `/gork enable` status and ensure it has `Message Content Intent` enabled in the Discord Developer Portal.
- **Image generation slow?** The Gemini model can take 15-30 seconds. Check console logs for "Requesting image".
- **Permission Denied?** Ensure you have the role named in `manager_role_name` (config.json).

---

## 📦 Gitignore Recommendation

Add these to your `.gitignore` to keep tokens and state safe:
```
config/config.json
data/state.json
.venv/
__pycache__/
*.pyc
```