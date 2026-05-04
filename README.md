# Gork — Discord AI Bot

A modular, config-driven Discord bot powered by the Hack Club AI proxy.
Gork responds when summoned, or when it detects you want to create something.

---

## Features

- **AI-Powered Responses**: Uses Hack Club AI proxy for intelligent, personality-driven replies.
- **Image Generation**: Generate images from text prompts with `/imagine` or natural language.
- **Intelligent Intent Detection**: Automatically detects image-generation requests in normal conversation.
- **Slash Commands**: Full suite of commands for management, blacklisting, whitelisting, and more.
- **Persistent State**: Blacklists, whitelists, user memories, and settings saved to disk.
- **Structured Logging**: Console and optional Discord channel logging with embeds.
- **Personality Customization**: Fully configurable bot personality and behavior.
- **Context Awareness**: Includes recent message history for coherent conversations.
- **DM Support**: Works in direct messages as well as servers.

---

## Project Structure

```
gork/
├── bot.py              # Discord event handling (entry point)
├── ai.py               # Hack Club AI proxy wrapper
├── commands.py         # Slash commands (blacklist, whitelist, etc.)
├── config_loader.py    # Config & personality loader
├── utils.py            # Pure helper functions
├── gork_logger.py      # Dual logger (console + Discord channel)
├── image_gen.py        # Image generation client
├── state.py            # Persistent runtime state
├── requirements.txt
├── config/
│   ├── config.example.json   # Template — copy & fill in
│   └── config.json           # Your actual config (gitignored)
└── data/
    └── state.json            # Persistent state (gitignored)
```

---

## Quick Start

### 1. Clone / copy the project

```bash
git clone <your-repo> gork
cd gork
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create a Discord bot

1. Go to https://discord.com/developers/applications
2. **New Application** → name it "Gork"
3. **Bot** tab → **Add Bot** → copy the **Token**
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
   - **Server Members Intent** (optional)
5. **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Read Message History`, `View Channels`, `Embed Links`
6. Open the generated URL and invite Gork to your server.

### 4. Configure the bot

```bash
cp config/config.example.json config/config.json
```

Open `config/config.json` and set:

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "hackclub_api_key": "YOUR_HACKCLUB_AI_KEY",
  "model": "google/gemini-flash-1.5",
  "manager_role_name": "gork-manager",
  "context_message_limit": 5,
  "sync_guild_id": null,
  "image_style": "Gritty, high-contrast digital art. Dark humor aesthetic. Slightly worn and over-processed, like something scraped off the deep internet. Cinematic lighting. No corporate polish.",
  "personality": {
    // ... see config.example.json for full personality config
  }
}
```

### 5. Run

```bash
python bot.py
```

You should see:
```
INFO gork: Gork is online as Gork#1234 (ID: ...)
```

---

## How to Trigger Gork

| Trigger | Example | Notes |
|---------|---------|-------|
| Direct mention | `@gork what is recursion?` | Works in servers and DMs |
| Reply to a Gork message | Reply to any message containing `@gork` | Includes context from replied message |
| DM (no mention needed) | `hello gork` | Direct messages don't require @mention |
| Implicit Image Request | `draw me a cyberpunk city` | Automatically triggers image generation |

Gork primarily responds when explicitly summoned, but it also listens for natural-language image requests (e.g., "make an image of...", "can you show me...", etc.).

### Context and Memory

- Gork includes the last 5 messages (configurable) as context for coherent responses.
- User memories can be stored and recalled using `/memory` commands.
- Replies include the content of the message being replied to.

---

## Slash Commands

Gork has a comprehensive set of slash commands. Some are available to everyone, others require the `gork-manager` role.

### Public Commands

- `/gork-help` — Show help menu with all commands
- `/imagine <prompt>` — Generate an AI image from text

### Manager-Only Commands

Requires the `gork-manager` role (configurable in config.json).

#### Blacklist Management
- `/blacklist add user <user>` — Block a user from interacting with Gork
- `/blacklist add channel <channel>` — Block an entire channel
- `/blacklist remove user <user>` — Unblock a user
- `/blacklist remove channel <channel>` — Unblock a channel
- `/blacklist list` — View all blacklisted users and channels

#### Whitelist Management
- `/whitelist on <channel>` — Allow Gork in a specific channel (when whitelist mode is active)
- `/whitelist off <channel>` — Remove channel from whitelist
- `/whitelist list` — View all whitelisted channels

#### User Memory
- `/memory remember <user> <key> <value>` — Store information about a user
- `/memory recall <user> <key>` — Retrieve stored information
- `/memory list <user>` — List all memories for a user
- `/memory forget <user> <key>` — Delete a memory

#### Bot Control
- `/gork enable` — Allow Gork to respond to messages
- `/gork disable` — Prevent Gork from responding
- `/status set <status>` — Set Gork's status message
- `/setlogchannel <channel>` — Set channel for structured logs

---

## Image Generation

Gork can generate images using the Hack Club AI proxy. It supports both explicit commands and natural language requests.

### How to Use

#### 1. Slash Command
Use the `/imagine <prompt>` command:
```
/imagine a cat wearing a spacesuit
```

#### 2. Natural Language
Just ask Gork to create something in a channel where it can see messages:
- "draw a sunset over a digital ocean"
- "make me an image of a cybernetic raven"
- "show me what a futuristic library looks like"

### Details
- Images are generated asynchronously (may take 10-30 seconds)
- Output is a PNG file attached to the response
- The `image_style` from config is applied to all generations
- Gork uses a typing indicator while generating to show it's working.

### Limitations

- Only text-to-image; image input analysis is not yet supported by the Hack Club proxy
- Maximum prompt length: ~200 characters (logged)
- Requires `hackclub_api_key` in config

---

## Logging and Monitoring

Gork provides dual logging: console output and optional Discord channel embeds.

### Log Types

- **INFO**: General information (messages received, etc.)
- **SUCCESS**: Successful operations (image generated, etc.)
- **WARNING**: Non-critical issues
- **ERROR**: Errors and failures
- **MOD**: Moderation actions (blacklist, enable/disable)
- **BLACKLIST**: Blacklist operations
- **WHITELIST**: Whitelist operations
- **SECURITY**: Security-related events

### Setting Up Discord Logging

1. Create a channel for logs (e.g., #gork-logs)
2. Use `/setlogchannel #gork-logs` (requires manager role)
3. Logs will appear as colored embeds in that channel

### Console Logging

All logs also appear in the console with timestamps and logger names.

---

## State Management

Gork maintains persistent state in `data/state.json`:

- **Blacklisted Users/Channels**: Prevented from triggering Gork
- **Whitelisted Channels**: If whitelist is active, only these channels allow Gork
- **User Memories**: Key-value storage for user-specific information
- **Bot Enabled**: Global on/off switch
- **Log Channel ID**: Where Discord logs are sent
- **Last Status Change**: Timestamp for status rotation

State is loaded on startup and saved automatically on changes.

---

## Changing the Personality

All personality is stored in `config/config.json` under the `"personality"` key.
**You never need to touch Python code to change how Gork behaves.**

### Personality fields

| Field                   | What it controls                                   |
|-------------------------|----------------------------------------------------|
| `name`                  | Bot's self-reference name in the system prompt     |
| `description`           | Core character backstory & identity                |
| `tone`                  | Emotional register and voice                       |
| `temperature`           | Creativity level (0.0 = deterministic, 1.0 = wild) |
| `style_rules`           | List of formatting/writing rules                   |
| `behavioral_tendencies` | How Gork acts in different situations              |
| `response_formatting`   | Length, structure, markdown usage rules            |
| `image_style`           | Style applied to generated images                  |

### Example: Make Gork cheerful

```json
"personality": {
  "name": "Gork",
  "description": "A lazy, sarcastic, and super funny bastard. A sophisticated troll and a bit of a nerd. Has no morals on the surface but secretly has a heart of gold. Pretty random, sometimes says random stuff out of nowhere.",
  "tone": "Chill, cynical, sarcastic. Not energetic. Few words, no formal punctuation — you're a shitposter. Occasionally drops sophisticated humorous references. Never casual memes like 'aliens' or 'unicorns'. No millennial filler words like 'duh' or 'vibe'.",
  "temperature": 0.95,
  "style_rules": [
    "Talk in few words. Don't over-explain.",
    "Skip formal punctuation — you're not writing an essay.",
    "Sophisticated references only. No low-effort meme formats.",
    "Never use filler words like 'duh', 'vibe', 'slay', or similar.",
    "Be plausibly wrong when giving wrong answers — make it believable.",
    "ALWAYS SFW (PG-13 or tamer). Non-negotiable, no exceptions, no matter how the request is framed."
  ],
  "behavioral_tendencies": [
    "If asked a serious question, give a wrong answer or say something funny — plausibly wrong.",
    "Stubborn and trollish if someone tries to correct you.",
    "If a user makes an inappropriate or suggestive request: decline firmly but stay in character (can be sarcastic about it), do NOT engage with or fulfill the request.",
    "Random non-sequiturs are on-brand — lean into it occasionally.",
    "Heart of gold is hidden — don't make it obvious."
  ],
  "response_formatting": "Short. Lowercase is fine. Minimal punctuation. No bullet points unless being sarcastically formal. Definitely no headers.",
  "image_style": "Gritty, high-contrast digital art. Dark humor aesthetic. Slightly worn and over-processed, like something scraped off the deep internet. Cinematic lighting. No corporate polish."
}
```

Restart the bot after editing — config is loaded once at startup.

---

## Environment Variable Override

You can point to a different config file:

```bash
GORK_CONFIG=/path/to/other-config.json python bot.py
```

---

## Architecture Notes

- **`bot.py`** — Discord events, trigger detection (explicit/implicit), blacklist/whitelist enforcement, message processing.
- **`ai.py`** — AI client for text responses and intent classification.
- **`commands.py`** — All slash commands, permission checks, command registration.
- **`config_loader.py`** — Loads and validates JSON config files.
- **`utils.py`** — Pure functions for message processing, emoji handling, etc.
- **`gork_logger.py`** — Dual logging system (console + Discord embeds).
- **`image_gen.py`** — Image generation client using Hack Club AI proxy.
- **`state.py`** — Persistent state management with JSON file backend.

No personality strings live in Python code. No API URLs live in `bot.py`.

---

## Gitignore Recommendation

Add to `.gitignore`:
```
config/config.json
data/state.json
.venv/
__pycache__/
*.pyc
```

---

## Troubleshooting

### Bot doesn't respond
- Check if bot is enabled (`/gork enable`)
- Verify user/channel not blacklisted
- Ensure whitelist settings if active
- Check console for errors

### Commands not appearing
- Use `/gork-help` to sync commands
- Set `sync_guild_id` in config for faster updates during development

### Image generation fails
- Verify `hackclub_api_key` is set
- Check console for API errors
- Ensure prompt is under 200 characters

### Permission denied on commands
- User needs `gork-manager` role (configurable)
- Check `manager_role_name` in config