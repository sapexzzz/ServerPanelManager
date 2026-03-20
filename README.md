# Modrinth Extractor

A script to download mods, resource packs, shaders, and datapacks from `modrinth.index.json` file (export from Modrinth / Prism Launcher modpack).

## Requirements

- Python 3.8+
- Package `requests`

```bash
pip install requests
```

## Usage

```bash
python extract.py modrinth.index.json
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `json_file` | — | Path to `modrinth.index.json` |
| `-o`, `--output` | `extract` | Output directory for downloaded files |
| `--retries` | `3` | Number of retry attempts on network error |
| `--skip-hash` | disabled | Skip SHA1/SHA512 verification |

### Examples

```bash
# Download to extract/ folder next to the script
python extract.py modrinth.index.json

# Specify a different output directory
python extract.py modrinth.index.json -o ~/Downloads/my_modpack

# 5 attempts, without hash verification
python extract.py modrinth.index.json --retries 5 --skip-hash
```

## Output Structure

```
extract/
├── mods/           # .jar — mod files
├── resourcepacks/  # .zip — resource packs
├── datapacks/      # datapacks
├── shaders/        # shaders
└── other/          # everything else
```

File category is determined by **path** in JSON (priority), then by extension and filename.

## Improvements over Original .sh Script

| Issue | Solution |
|---|---|
| `pkg install` — Termux-specific only | Only standard `requests` package |
| `while read` in subshell → counter always 0 | Regular Python loop without subshell |
| No retry attempts on failure | 3 attempts + exponential backoff |
| Hash verified even if wget failed | Hash only checked after successful download |
| SHA1 only | SHA512 → SHA1 (priority by Modrinth standard) |
| Re-downloads already fetched files | Files with correct hash are skipped |
| Datapacks misclassified as resourcepacks | Detection by path + extension + filename |
| Incomplete files left on disk | Deleted on failure or hash mismatch |
| No error summary | List of failed files at the end + `exit 1` |
| No pack information | Displays pack name, version, and Minecraft version |

## License

MIT
