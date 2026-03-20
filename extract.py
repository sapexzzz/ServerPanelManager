#!/usr/bin/env python3
"""
Modrinth Index Extractor
Downloads files from modrinth.index.json with SHA1/SHA512 verification.
"""

import sys
import json
import hashlib
import argparse
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Package 'requests' is required. Install it: pip install requests")

# ── ANSI colors ────────────────────────────────────────────────────────────────
RED    = "\033[31m"
GREEN  = "\033[32m"
BLUE   = "\033[34m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def progress_bar(current: int, total: int, width: int = 22) -> str:
    pct = current / total if total else 0
    filled = int(pct * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {int(pct * 100):3d}%"


def detect_dir(path_in_file: str, basename: str) -> str:
    """
    Determines file category by path and extension.
    Logic: first check path (directory), then extension.
    """
    lower_path = path_in_file.lower()
    ext = Path(basename).suffix.lower()

    # By path
    if "/datapack" in lower_path or "datapacks/" in lower_path:
        return "datapacks"
    if "/resourcepack" in lower_path or "resourcepacks/" in lower_path:
        return "resourcepacks"
    if "/shader" in lower_path or "shaderpacks/" in lower_path:
        return "shaders"
    if "/mod" in lower_path or "mods/" in lower_path:
        return "mods"

    # By extension
    if ext == ".jar":
        return "mods"
    if ext in (".zip", ".mrpack"):
        name_lower = basename.lower()
        if "shader" in name_lower:
            return "shaders"
        if "datapack" in name_lower or "data_pack" in name_lower:
            return "datapacks"
        return "resourcepacks"
    if ext in (".mcpack",):
        return "datapacks"

    return "other"


def verify_hash(file_path: Path, expected: str, algo: str = "sha1") -> bool:
    h = hashlib.new(algo)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest() == expected


def download_file(url: str, dest: Path, retries: int = 3, timeout: int = 30) -> bool:
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            return True
        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(2 ** attempt)  # exponential backoff
            else:
                print(f"  {RED}Download error ({attempt}/{retries}): {e}{RESET}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Downloads mods/resources from modrinth.index.json"
    )
    parser.add_argument("json_file", help="Path to modrinth.index.json")
    parser.add_argument(
        "-o", "--output", default="extract",
        help="Output directory (default: extract)"
    )
    parser.add_argument(
        "--retries", type=int, default=3,
        help="Number of retries on error (default: 3)"
    )
    parser.add_argument(
        "--skip-hash", action="store_true",
        help="Skip hash verification"
    )
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.is_file():
        sys.exit(f"{RED}File '{json_path}' not found!{RESET}")

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{RED}JSON parse error: {e}{RESET}")

    files = data.get("files", [])
    total = len(files)
    if total == 0:
        sys.exit(f"{YELLOW}No files to download.{RESET}")

    pack_name = data.get("name", "unknown pack")
    pack_ver  = data.get("versionId", "")
    mc_ver    = data.get("dependencies", {}).get("minecraft", "")

    print(f"\n{BOLD}{BLUE}{'━' * 50}{RESET}")
    print(f"{BOLD}  Modrinth Extractor{RESET}")
    print(f"  Pack    : {CYAN}{pack_name}{RESET} {pack_ver}")
    if mc_ver:
        print(f"  Minecraft : {CYAN}{mc_ver}{RESET}")
    print(f"  Files   : {CYAN}{total}{RESET}")
    print(f"  Output  : {CYAN}{args.output}{RESET}")
    print(f"{BOLD}{BLUE}{'━' * 50}{RESET}\n")

    extract_dir = Path(args.output)
    for subdir in ("mods", "resourcepacks", "datapacks", "shaders", "other"):
        (extract_dir / subdir).mkdir(parents=True, exist_ok=True)

    ok_count   = 0
    fail_count = 0
    failures: list[str] = []

    for idx, entry in enumerate(files, start=1):
        path_in_file = entry.get("path", "unknown")
        downloads    = entry.get("downloads", [])
        hashes       = entry.get("hashes", {})
        basename     = Path(path_in_file).name

        if not downloads:
            print(f"  {RED}[{idx}/{total}] No URL for: {basename}{RESET}")
            fail_count += 1
            failures.append(basename)
            continue

        url = downloads[0]
        category = detect_dir(path_in_file, basename)
        dest     = extract_dir / category / basename

        bar = progress_bar(idx - 1, total)
        print(f"{YELLOW}{bar}{RESET} [{idx}/{total}] {CYAN}{basename}{RESET}", end="", flush=True)

        # Skip already downloaded (fast cache check)
        already_ok = False
        if dest.exists() and not args.skip_hash:
            for algo in ("sha512", "sha1"):
                expected = hashes.get(algo)
                if expected and verify_hash(dest, expected, algo):
                    already_ok = True
                    break

        if already_ok:
            print(f"  {GREEN}(cached){RESET}")
            ok_count += 1
            continue

        success = download_file(url, dest, retries=args.retries)

        if not success:
            print(f"  {RED}✗ download failed{RESET}")
            fail_count += 1
            failures.append(basename)
            if dest.exists():
                dest.unlink()          # remove incomplete file
            continue

        # Hash verification
        if args.skip_hash:
            print(f"  {GREEN}✔{RESET}")
            ok_count += 1
            continue

        hash_ok = False
        for algo in ("sha512", "sha1"):
            expected = hashes.get(algo)
            if expected:
                hash_ok = verify_hash(dest, expected, algo)
                break

        if hash_ok or not hashes:
            print(f"  {GREEN}✔{RESET}")
            ok_count += 1
        else:
            print(f"  {RED}✗ hash mismatch{RESET}")
            fail_count += 1
            failures.append(basename)
            dest.unlink(missing_ok=True)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{BLUE}{'━' * 50}{RESET}")
    print(f"  {GREEN}Success : {ok_count}{RESET}")
    if fail_count:
        print(f"  {RED}Errors  : {fail_count}{RESET}")
        for name in failures:
            print(f"    {RED}• {name}{RESET}")
    print(f"  Files at: {CYAN}{extract_dir.resolve()}{RESET}")
    print(f"{BOLD}{BLUE}{'━' * 50}{RESET}\n")

    if fail_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
