# Minecraft Server Panel Manager

A cross-platform interactive terminal panel for managing a Fabric (or vanilla) Minecraft server via **tmux**. Written in Python 3.

---

## Features

| # | Feature |
|---|---------|
| 1 | Start / Stop / Restart / Kill server |
| 2 | Attach to live server console |
| 3 | Server status (RUNNING / STOPPED) |
| 4 | View live server logs |
| 5 | Create timestamped world backups (`.tar.gz`) |
| 6 | Mods manager — enable / disable `.jar` files |
| 7 | Edit `server.properties` in your preferred editor |
| 8 | Change allocated RAM on the fly |
| 9 | Toggle auto-restart after crash |
| 10 | Live CPU / RAM / uptime monitor |
| 11 | Delete server or monitor logs |
| 12 | Whitelist manager (add / remove players) |

---

## Requirements

### System packages

| Package | Purpose |
|---------|---------|
| `tmux` | Server session management |
| `java` (21+) | Running the Minecraft server |
| `tar` / `gzip` | World backups (usually pre-installed) |
| `nano` or `$EDITOR` | Editing `server.properties` |

**Debian / Ubuntu:**
```bash
sudo apt install tmux openjdk-21-jre-headless
```

**Arch Linux:**
```bash
sudo pacman -S tmux jdk21-openjdk
```

**Fedora / RHEL:**
```bash
sudo dnf install tmux java-21-openjdk-headless
```

### Python packages

```bash
pip install -r requirements.txt
```

> `psutil` is optional but recommended — the resources monitor falls back to system commands (`free`, `top`) without it.

---

## Setup

1. **Clone / copy** the project into any directory, e.g. `~/scripts/Panel_manager/`.

2. **Edit the configuration** at the top of `menu.py`:

   ```python
   BASE_DIR  = Path.home() / "mc"          # path to your server folder
   JAR_NAME  = "fabric-server-mc.*.jar"    # exact jar filename
   JAVA_RAM  = "2G"                        # RAM allocated to the server
   ```

3. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Make the script executable** (optional):

   ```bash
   chmod +x menu.py
   ```

---

## Usage

```bash
python3 menu.py
# or, if marked executable:
./menu.py
```

Navigate the menu using number keys and press **Enter**.

### Detaching from the console

While attached to the server console via tmux, press **Ctrl-B**, then **D** to detach and return to the panel.

---

## Directory structure expected

```
<BASE_DIR>/
├── <JAR_NAME>          # server jar
├── server.properties
├── whitelist.json
├── world/              # world data
├── mods/               # active mods
├── disabled_mods/      # disabled mods
├── backups/            # auto-created, world archives
└── server.log          # server output log
```

---

## Notes

- The panel runs entirely in the current terminal. The Minecraft server itself runs inside a detached tmux session.
- Changing RAM or auto-restart within the panel takes effect on the **next** server start.
- The `whitelist.json` format is compatible with vanilla Minecraft (UUID + name pairs).

---

## License

MIT — use freely.
