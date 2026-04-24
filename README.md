# Gork — Discord AI Bot

A modular, config-driven Discord bot powered by the Hack Club AI proxy.
Gork responds only when explicitly summoned — no passive eavesdropping.

---

## Project Structure

```
gork/
├── bot.py              # Discord event handling (entry point)
├── ai.py               # Hack Club AI proxy wrapper
├── config_loader.py    # Config & personality loader
├── utils.py            # Pure helper functions
├── requirements.txt
└── config/
    ├── config.example.json   # Template — copy & fill in
    └── config.json           # Your actual config (gitignored)
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
python3.10 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create your Discord bot

1. Go to https://discord.com/developers/applications
2. **New Application** → name it "Gork"
3. **Bot** tab → **Add Bot** → copy the **Token**
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
   - **Server Members Intent** (optional)
5. **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Read Message History`, `View Channels`
6. Open the generated URL and invite Gork to your server.

### 4. Configure the bot

```bash
cp config/config.example.json config/config.json
```

Open `config/config.json` and set:

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "hackclub_api_key": "",          // Leave empty — Hack Club proxy is open
  ...
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

| Trigger | Example |
|---------|---------|
| Direct mention | `@gork what is recursion?` |
| Reply to a Gork message | Reply to any message containing `@gork` |
| With image | `@gork what's in this image?` (+ attach image) |

Gork **ignores all other messages** — no passive reading.

---

## Image Processing

Gork can now process images! When you include an image in your message, Gork will analyze it and respond accordingly.

### Supported Image Formats

- PNG
- JPEG/JPG
- GIF
- WebP

### How to Use

Simply attach an image to your message when mentioning or replying to Gork:

```
@gork what's in this image?
[attach image]
```

Or reply to a Gork message with an image:

```
Reply to Gork message
[attach image]
what do you think about this?
```

### Limitations

- Maximum image size: 20 MB
- Up to 10+ images can be processed per message (model-dependent)
- The AI will analyze the image and respond in text form

---

## Changing the Personality

All personality is stored in `config/config.json` under the `"personality"` key.
**You never need to touch Python code to change how Gork behaves.**

### Personality fields

| Field | What it controls |
|-------|-----------------|
| `name` | Bot's self-reference name in the system prompt |
| `description` | Core character backstory & identity |
| `tone` | Emotional register and voice |
| `temperature` | Creativity level (0.0 = deterministic, 1.0 = wild) |
| `style_rules` | List of formatting/writing rules |
| `behavioral_tendencies` | How Gork acts in different situations |
| `response_formatting` | Length, structure, markdown usage rules |

### Example: Make Gork cheerful

```json
"personality": {
  "name": "Gork",
  "description": "Gork is an enthusiastic, endlessly optimistic helper who genuinely loves answering questions.",
  "tone": "Warm, upbeat, encouraging — like a brilliant friend who is always happy to help.",
  "temperature": 0.7,
  "style_rules": [
    "Start every response with a brief, genuine acknowledgment.",
    "Use positive framing wherever possible.",
    "Emojis are welcome but not excessive — max two per response."
  ],
  "behavioral_tendencies": [
    "Celebrates user curiosity.",
    "Offers follow-up suggestions proactively.",
    "Never makes the user feel silly for asking."
  ],
  "response_formatting": "Warm paragraphs. Lists for 3+ items. Keep it human and readable."
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

- **`bot.py`** — Only Discord logic. Detects triggers, calls `ai.py`, sends chunks.
- **`ai.py`** — Only AI logic. Builds prompts, calls Hack Club API, parses responses.
- **`config_loader.py`** — Only I/O. Reads and validates JSON config.
- **`utils.py`** — Pure functions. No side effects, fully testable.

No personality strings live in Python code. No API URLs live in `bot.py`.

---

## Gitignore Recommendation

Add to `.gitignore`:
```
config/config.json
.venv/
__pycache__/
*.pyc
```
