#!/usr/bin/env python3
"""
Minecraft Server Panel Manager
A cross-platform terminal panel for managing a Fabric Minecraft server via tmux.

Requires: Python 3.8+, tmux, java, tar
Install Python deps: pip install -r requirements.txt
"""

import os
import sys
import json
import time
import uuid
import shutil
import subprocess
import datetime
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# ─────────────────────── Configuration ──────────────────────────────────────
# Config is stored in panel_config.json next to this script.
# On first run a setup wizard will prompt you for all values.

CONFIG_FILE = Path(__file__).resolve().parent / "panel_config.json"

DEFAULT_CONFIG: dict = {
    "base_dir":     str(Path.home() / "mc"),
    "jar_name":     "fabric-server-mc.1.20.1-loader.0.18.1-launcher.1.1.0.jar",
    "session_name": "mcserver",
    "java_ram":     "2G",
    "auto_restart": False,
}

# Globals — populated by apply_config() before main_menu() runs
BASE_DIR:          Path
JAR_NAME:          str
SESSION_NAME:      str
JAVA_RAM:          str
AUTO_RESTART:      bool
BACKUP_DIR:        Path
MODS_DIR:          Path
DISABLED_MODS_DIR: Path
WORLD_DIR:         Path
LOG_FILE:          Path
RES_LOG_FILE:      Path


def apply_config(cfg: dict) -> None:
    """Write every config value into module-level globals."""
    global BASE_DIR, JAR_NAME, SESSION_NAME, JAVA_RAM, AUTO_RESTART
    global BACKUP_DIR, MODS_DIR, DISABLED_MODS_DIR, WORLD_DIR, LOG_FILE, RES_LOG_FILE
    BASE_DIR          = Path(cfg["base_dir"])
    JAR_NAME          = cfg["jar_name"]
    SESSION_NAME      = cfg["session_name"]
    JAVA_RAM          = cfg["java_ram"]
    AUTO_RESTART      = bool(cfg["auto_restart"])
    BACKUP_DIR        = BASE_DIR / "backups"
    MODS_DIR          = BASE_DIR / "mods"
    DISABLED_MODS_DIR = BASE_DIR / "disabled_mods"
    WORLD_DIR         = BASE_DIR / "world"
    LOG_FILE          = BASE_DIR / "server.log"
    RES_LOG_FILE      = BASE_DIR / "resources.log"


def load_config() -> dict:
    if CONFIG_FILE.is_file():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            # Fill missing keys from defaults
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# ─────────────────────── ANSI Colors ─────────────────────────────────────────

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def pause() -> None:
    input("Press Enter to continue...")


def clear() -> None:
    os.system("clear")


# ─────────────────────── tmux helpers ────────────────────────────────────────

def tmux_has_session() -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", SESSION_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def require_tmux() -> None:
    if shutil.which("tmux") is None:
        print(f"{YELLOW}tmux not found. Please install it:{RESET}")
        print("  Debian/Ubuntu : sudo apt install tmux")
        print("  Arch Linux    : sudo pacman -S tmux")
        print("  Fedora/RHEL   : sudo dnf install tmux")
        print("  macOS         : brew install tmux")
        sys.exit(1)


# ─────────────────────── Server control ──────────────────────────────────────

def start_server() -> None:
    require_tmux()
    if tmux_has_session():
        print(f"{YELLOW}Server is already running.{RESET}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    runner = BASE_DIR / ".server_runner.sh"
    auto_flag = "yes" if AUTO_RESTART else "no"

    runner.write_text(
        f"""#!/usr/bin/env bash
cd "{BASE_DIR}"
JAVA_CMD=(java -Xmx{JAVA_RAM} -jar "{JAR_NAME}" nogui)
while true; do
  echo "[server-runner] Starting: ${{JAVA_CMD[*]}}" | tee -a "{LOG_FILE}"
  "${{JAVA_CMD[@]}}" 2>&1 | tee -a "{LOG_FILE}"
  EXITCODE=$?
  echo "[server-runner] Server stopped with exit code $EXITCODE" | tee -a "{LOG_FILE}"
  if [ "{auto_flag}" != "yes" ]; then
    echo "[server-runner] AUTO_RESTART disabled. Exiting." | tee -a "{LOG_FILE}"
    break
  fi
  echo "[server-runner] Restarting in 5 seconds..." | tee -a "{LOG_FILE}"
  sleep 5
done
"""
    )
    runner.chmod(0o755)
    subprocess.run(["tmux", "new-session", "-d", "-s", SESSION_NAME, str(runner)])
    time.sleep(0.5)
    print(f"{GREEN}Server started in tmux session '{SESSION_NAME}'.{RESET}")


def stop_server() -> None:
    if not tmux_has_session():
        print(f"{YELLOW}Server is not running.{RESET}")
        return
    print(f"{YELLOW}Stopping server...{RESET}")
    subprocess.run(["tmux", "send-keys", "-t", SESSION_NAME, "stop", "Enter"])
    for _ in range(20):
        if not tmux_has_session():
            print(f"{GREEN}Server stopped.{RESET}")
            return
        time.sleep(1)
    print(f"{RED}Could not stop server gracefully. Killing tmux session.{RESET}")
    subprocess.run(["tmux", "kill-session", "-t", SESSION_NAME])


def restart_server() -> None:
    stop_server()
    start_server()


def console_server() -> None:
    require_tmux()
    if tmux_has_session():
        print(f"{GREEN}Attaching to server console... (detach: Ctrl-B D){RESET}")
        subprocess.run(["tmux", "attach-session", "-t", SESSION_NAME])
    else:
        print(f"{RED}Server is not running.{RESET}")


def kill_server() -> None:
    if tmux_has_session():
        subprocess.run(["tmux", "kill-session", "-t", SESSION_NAME])
        print(f"{RED}tmux session killed.{RESET}")
    else:
        print(f"{YELLOW}No active session found.{RESET}")


def status_server() -> None:
    print("=" * 48)
    print()
    if tmux_has_session():
        print(f"           Status: {GREEN}RUNNING{RESET}")
    else:
        print(f"           Status: {RED}STOPPED{RESET}")
    print()
    print("=" * 48)


# ─────────────────────── Backup ──────────────────────────────────────────────

def backup_world() -> None:
    if not WORLD_DIR.is_dir():
        print(f"{RED}World directory not found: {WORLD_DIR}{RESET}")
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"world-{timestamp}.tar.gz"
    try:
        subprocess.run(
            ["tar", "-czf", str(target), "-C", str(BASE_DIR), WORLD_DIR.name],
            check=True,
        )
        print(f"{GREEN}Backup created: {target}{RESET}")
    except subprocess.CalledProcessError:
        print(f"{RED}Backup failed.{RESET}")


# ─────────────────────── Mods manager ────────────────────────────────────────

def mods_list() -> None:
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    DISABLED_MODS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{'FILENAME':<55} STATUS")
    print("=" * 66)
    for f in sorted(MODS_DIR.glob("*.jar")):
        print(f"{f.name:<55} {GREEN}ENABLED{RESET}")
    print("=" * 66)
    for f in sorted(DISABLED_MODS_DIR.glob("*.jar")):
        print(f"{f.name:<55} {RED}DISABLED{RESET}")
    print("=" * 66)


def mods_disable() -> None:
    name = input("Mod filename to disable: ").strip()
    src = MODS_DIR / name
    if src.is_file():
        shutil.move(str(src), str(DISABLED_MODS_DIR / name))
        print(f"{YELLOW}Mod disabled: {name}{RESET}")
    else:
        print(f"{RED}File not found in mods directory.{RESET}")


def mods_enable() -> None:
    name = input("Mod filename to enable: ").strip()
    src = DISABLED_MODS_DIR / name
    if src.is_file():
        shutil.move(str(src), str(MODS_DIR / name))
        print(f"{GREEN}Mod enabled: {name}{RESET}")
    else:
        print(f"{RED}File not found in disabled_mods directory.{RESET}")


def mods_manager() -> None:
    while True:
        clear()
        print("=" * 48)
        print("            Mods Manager")
        print("=" * 48)
        mods_list()
        print("1) Disable mod")
        print("2) Enable mod")
        print("3) Back")
        print("=" * 48)
        choice = input("Select: ").strip()
        if choice == "1":
            mods_disable()
            pause()
        elif choice == "2":
            mods_enable()
            pause()
        elif choice == "3":
            break
        else:
            print("Invalid choice.")
            time.sleep(1)


# ─────────────────────── Logs ────────────────────────────────────────────────

def view_logs() -> None:
    if not LOG_FILE.is_file():
        print(f"{YELLOW}Log file not found: {LOG_FILE}{RESET}")
        return
    print(f"{GREEN}Server logs — Ctrl-C to exit{RESET}")
    try:
        subprocess.run(["tail", "-n", "200", "-f", str(LOG_FILE)])
    except KeyboardInterrupt:
        pass


def delete_logs() -> None:
    print("1) Delete server logs")
    print("2) Delete monitor logs")
    d = input("Select: ").strip()
    if d == "1":
        if LOG_FILE.is_file():
            LOG_FILE.unlink()
            print(f"{GREEN}Server logs deleted.{RESET}")
        else:
            print("No server log file found.")
    elif d == "2":
        if RES_LOG_FILE.is_file():
            RES_LOG_FILE.unlink()
            print(f"{GREEN}Monitor logs deleted.{RESET}")
        else:
            print("No monitor log file found.")
    else:
        print("Invalid choice.")


# ─────────────────────── Settings ────────────────────────────────────────────

def edit_properties() -> None:
    prop_file = BASE_DIR / "server.properties"
    prop_file.touch(exist_ok=True)
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(prop_file)])


def change_ram() -> None:
    global JAVA_RAM
    mem = input(f"Enter new RAM amount (current: {JAVA_RAM}, e.g. 4G): ").strip()
    if mem:
        JAVA_RAM = mem
        print(f"{GREEN}RAM set to {JAVA_RAM}.{RESET}")


def toggle_autorestart() -> None:
    global AUTO_RESTART
    AUTO_RESTART = not AUTO_RESTART
    state = f"{GREEN}ENABLED{RESET}" if AUTO_RESTART else f"{RED}DISABLED{RESET}"
    print(f"Auto-restart: {state}")


# ─────────────────────── Resources monitor ───────────────────────────────────

def _resources_psutil() -> str:
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    uptime_td = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))
    lines = [
        f"RAM : {mem.total // 2**20} MB total | "
        f"{mem.used // 2**20} MB used | "
        f"{mem.available // 2**20} MB free",
        f"CPU : {cpu:.1f}% used",
        f"Uptime: {uptime_td}",
    ]
    return "\n".join(lines)


def _resources_fallback() -> str:
    lines: list[str] = []
    free = subprocess.run(["free", "-m"], capture_output=True, text=True)
    for line in free.stdout.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            lines.append(
                f"RAM : {parts[1]} MB total | {parts[2]} MB used | {parts[3]} MB free"
            )
    top = subprocess.run(["top", "-bn1"], capture_output=True, text=True)
    for line in top.stdout.splitlines():
        if "%Cpu" in line or "Cpu(s)" in line:
            lines.append(f"CPU : {line.strip()}")
            break
    uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
    lines.append(f"Uptime: {uptime.stdout.strip()}")
    return "\n".join(lines)


def resources_monitor() -> None:
    print(f"{GREEN}Resources monitor — Ctrl-C to exit{RESET}")
    time.sleep(0.5)
    try:
        while True:
            clear()
            print("=" * 48)
            print("        Resources Monitor")
            print("=" * 48)
            if PSUTIL_AVAILABLE:
                print(_resources_psutil())
            else:
                print(_resources_fallback())
            print("=" * 48)
            time.sleep(1)
    except KeyboardInterrupt:
        pass


# ─────────────────────── Whitelist manager ───────────────────────────────────

def whitelist_manager() -> None:
    wl_file = BASE_DIR / "whitelist.json"
    if not wl_file.is_file():
        wl_file.write_text("[]")

    while True:
        clear()
        print("=" * 48)
        print("          Whitelist Manager")
        print("=" * 48)
        print("1) Show list")
        print("2) Add player")
        print("3) Remove player")
        print("4) Back")
        print("=" * 48)
        choice = input("Select: ").strip()

        wl: list[dict] = json.loads(wl_file.read_text())

        if choice == "1":
            if wl:
                for entry in wl:
                    print(f"  {entry.get('name', '?')}")
            else:
                print("Whitelist is empty.")
            pause()

        elif choice == "2":
            name = input("Player name to add: ").strip()
            if name:
                if any(p.get("name") == name for p in wl):
                    print(f"{YELLOW}Player '{name}' is already in the whitelist.{RESET}")
                else:
                    wl.append({"uuid": str(uuid.uuid4()), "name": name})
                    wl_file.write_text(json.dumps(wl, indent=2))
                    print(f"{GREEN}Player '{name}' added.{RESET}")
            pause()

        elif choice == "3":
            name = input("Player name to remove: ").strip()
            if name:
                new_wl = [p for p in wl if p.get("name") != name]
                wl_file.write_text(json.dumps(new_wl, indent=2))
                print(f"{YELLOW}Player '{name}' removed.{RESET}")
            pause()

        elif choice == "4":
            break
        else:
            print("Invalid choice.")
            time.sleep(1)


# ─────────────────────── Setup wizard ───────────────────────────────────────

def _ask(prompt: str, current: str) -> str:
    """Show current value, return new value (or keep current on empty input)."""
    val = input(f"  {prompt}\n  Current : {YELLOW}{current}{RESET}\n  New     : ").strip()
    return val if val else current


def setup_wizard(is_reconfigure: bool = False) -> None:
    global AUTO_RESTART
    clear()
    print(f"{BOLD}{BLUE}╔══════════════════════════════════════════════╗{RESET}")
    if is_reconfigure:
        print(f"{BOLD}{BLUE}║            Reconfigure Panel                 ║{RESET}")
    else:
        print(f"{BOLD}{BLUE}║          First-Run Setup Wizard              ║{RESET}")
    print(f"{BOLD}{BLUE}╚══════════════════════════════════════════════╝{RESET}")
    print()
    print("Press Enter to keep the current value, or type a new one.")
    print()

    cfg = load_config()

    print(f"{BOLD}[1/5] Server directory (BASE_DIR){RESET}")
    print("      All paths below are relative to this directory.")
    cfg["base_dir"] = _ask("Path to server folder:", cfg["base_dir"])
    print()

    print(f"{BOLD}[2/5] Server JAR filename (JAR_NAME){RESET}")
    print("      Only the filename, e.g. fabric-server-mc.1.21-loader.jar")
    # Show .jar files found in base_dir to help the user
    _base = Path(cfg["base_dir"])
    found_jars = sorted(_base.glob("*.jar")) if _base.is_dir() else []
    if found_jars:
        print(f"      {GREEN}Found .jar files in that folder:{RESET}")
        for j in found_jars:
            print(f"        • {j.name}")
    cfg["jar_name"] = _ask("JAR filename:", cfg["jar_name"])
    print()

    print(f"{BOLD}[3/5] tmux session name (SESSION_NAME){RESET}")
    cfg["session_name"] = _ask("Session name:", cfg["session_name"])
    print()

    print(f"{BOLD}[4/5] Java heap size (JAVA_RAM){RESET}")
    print("      Examples: 2G, 4G, 512M")
    cfg["java_ram"] = _ask("RAM amount:", cfg["java_ram"])
    print()

    print(f"{BOLD}[5/5] Auto-restart on crash{RESET}")
    ar_current = "yes" if cfg["auto_restart"] else "no"
    ar_input = _ask("Auto-restart? (yes/no):", ar_current).lower()
    cfg["auto_restart"] = ar_input in ("yes", "y", "1", "true")
    print()

    # Summary
    _base_p = Path(cfg["base_dir"])
    print(f"{BOLD}Summary:{RESET}")
    print(f"  Base dir    : {GREEN}{cfg['base_dir']}{RESET}")
    print(f"  JAR         : {GREEN}{cfg['jar_name']}{RESET}")
    print(f"  Session     : {GREEN}{cfg['session_name']}{RESET}")
    print(f"  RAM         : {GREEN}{cfg['java_ram']}{RESET}")
    print(f"  Auto-restart: {GREEN}{'yes' if cfg['auto_restart'] else 'no'}{RESET}")
    print()
    print(f"  Derived paths (auto)")
    print(f"    backups      → {_base_p / 'backups'}")
    print(f"    mods         → {_base_p / 'mods'}")
    print(f"    disabled_mods→ {_base_p / 'disabled_mods'}")
    print(f"    world        → {_base_p / 'world'}")
    print(f"    server.log   → {_base_p / 'server.log'}")
    print()
    confirm = input("Save and continue? [Y/n]: ").strip().lower()
    if confirm in ("", "y", "yes"):
        save_config(cfg)
        apply_config(cfg)
        print(f"{GREEN}Configuration saved to {CONFIG_FILE}{RESET}")
        time.sleep(1)
    else:
        print(f"{YELLOW}Cancelled — using previous configuration.{RESET}")
        time.sleep(1)


# ─────────────────────── Main menu ───────────────────────────────────────────

def main_menu() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    DISABLED_MODS_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        clear()
        auto_str = f"{GREEN}ON{RESET}" if AUTO_RESTART else f"{RED}OFF{RESET}"
        print(f"{BOLD}{BLUE}╔══════════ Minecraft Server Panel ══════════╗{RESET}")
        print(f"{BOLD}{BLUE}║       Mentality's Server Panel Manager     ║{RESET}")
        print(f"{BOLD}{BLUE}╚════════════════════════════════════════════╝{RESET}")
        print()
        print(f" {GREEN} 1{RESET}.  Start server")
        print(f" {GREEN} 2{RESET}.  Server console")
        print(f" {GREEN} 3{RESET}.  Stop server")
        print(f" {GREEN} 4{RESET}.  Kill tmux session")
        print(f" {GREEN} 5{RESET}.  Server status")
        print(f" {GREEN} 6{RESET}.  View logs")
        print(f" {GREEN} 7{RESET}.  Create world backup")
        print(f" {GREEN} 8{RESET}.  Mods manager")
        print(f" {GREEN} 9{RESET}.  Restart server")
        print(f" {GREEN}10{RESET}.  Edit server.properties")
        print(f" {GREEN}11{RESET}.  Change RAM             (current: {JAVA_RAM})")
        print(f" {GREEN}12{RESET}.  Toggle auto-restart    (current: {auto_str})")
        print(f" {GREEN}13{RESET}.  Resources monitor")
        print(f" {GREEN}14{RESET}.  Delete logs")
        print(f" {GREEN}15{RESET}.  Whitelist manager")
        print(f" {GREEN}16{RESET}.  Reconfigure panel")
        print(f" {GREEN}17{RESET}.  Exit")
        print()
        choice = input("Select action: ").strip()

        if choice == "1":
            start_server(); pause()
        elif choice == "2":
            console_server()
        elif choice == "3":
            stop_server(); pause()
        elif choice == "4":
            kill_server(); pause()
        elif choice == "5":
            status_server(); pause()
        elif choice == "6":
            view_logs()
        elif choice == "7":
            backup_world(); pause()
        elif choice == "8":
            mods_manager()
        elif choice == "9":
            restart_server(); pause()
        elif choice == "10":
            edit_properties()
        elif choice == "11":
            change_ram(); pause()
        elif choice == "12":
            toggle_autorestart(); pause()
        elif choice == "13":
            resources_monitor()
        elif choice == "14":
            delete_logs(); pause()
        elif choice == "15":
            whitelist_manager()
        elif choice == "16":
            setup_wizard(is_reconfigure=True)
        elif choice == "17":
            print("Bye!")
            sys.exit(0)
        else:
            print(f"{RED}Invalid choice.{RESET}")
            time.sleep(1)


# ─────────────────────── Entry point ─────────────────────────────────────────

if __name__ == "__main__":
    cfg = load_config()
    apply_config(cfg)
    # Run wizard if: no config file yet, or BASE_DIR doesn't exist
    if not CONFIG_FILE.is_file() or not BASE_DIR.is_dir():
        setup_wizard()
    main_menu()
