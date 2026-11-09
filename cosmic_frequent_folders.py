#!/usr/bin/env python3
"""
cosmic-frequent-folders: Dynamically populates COSMIC Files sidebar favorites
with the most frequently and recently used folders (Windows Quick Access style).
"""

import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

HOME = Path.home()
COSMIC_FAVORITES = HOME / ".config/cosmic/com.system76.CosmicFiles/v1/favorites"
XBEL_PATH = HOME / ".local/share/recently-used.xbel"
USER_DIRS_PATH = HOME / ".config/user-dirs.dirs"
CONFIG_PATH = HOME / ".config/cosmic-frequent-folders/config.json"

COSMIC_ENUMS = {"Home", "Documents", "Downloads", "Music", "Pictures", "Videos", "Desktop"}
RON_PATH_RE = re.compile(r'^Path\("((?:[^"\\]|\\.)*)"\)$')

DEFAULT_CONFIG = {
    "pinned": [
        "Home",
        "Documents",
        "Downloads",
        "Pictures",
        "/run/media/christian/NextcloudData/Nextcloud/Dokumente/Programmieren",
    ],
    "last_dynamic": [],
    "max_dynamic": 4,
    "half_life_days": 7.0,
    "use_zoxide": True,
    "sync_gui_favorites": True,
    "exclude_prefixes": [
        "/tmp",
        "/var",
        "/proc",
        "/sys",
        "/dev",
        "/run/user",
    ],
    "exclude_names": [
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "target",
        "build",
        "dist",
        ".cache",
        ".local",
        ".config",
        ".gemini",
        ".thunderbird",
        ".mozilla",
        ".steam",
    ],
}


def parse_ron_favorites(ron_text: str) -> list[str]:
    """Parse COSMIC Files favorites RON list into enum names or path strings."""
    items: list[str] = []
    for raw_line in ron_text.splitlines():
        line = raw_line.strip().rstrip(",").strip()
        if not line or line in ("[", "]"):
            continue
        if line in COSMIC_ENUMS:
            items.append(line)
            continue
        m = RON_PATH_RE.match(line)
        if m:
            unescaped = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
            items.append(unescaped)
    return items


def load_config(config_path: Path = CONFIG_PATH) -> dict:
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        merged.update(data)
        return merged
    except Exception as exc:
        print(f"Warning: Failed to read {config_path} ({exc}), using defaults.", file=sys.stderr)
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(config: dict, config_path: Path = CONFIG_PATH) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sync_gui_pins(config: dict, favorites_path: Path = COSMIC_FAVORITES) -> None:
    """Preserve favorites manually added or removed by the user in COSMIC Files GUI."""
    if not config.get("sync_gui_favorites", True) or not favorites_path.exists():
        return
    try:
        current_items = parse_ron_favorites(favorites_path.read_text(encoding="utf-8"))
    except OSError:
        return
    if not current_items:
        return

    last_dyn = set(config.get("last_dynamic", []))
    gui_pinned = [item for item in current_items if item not in last_dyn]
    if gui_pinned:
        config["pinned"] = gui_pinned


def resolve_xdg_dirs() -> dict[str, Path]:
    mapping = {
        "Home": HOME,
        "Desktop": HOME / "Desktop",
        "Downloads": HOME / "Downloads",
        "Documents": HOME / "Documents",
        "Music": HOME / "Music",
        "Pictures": HOME / "Pictures",
        "Videos": HOME / "Videos",
    }
    key_map = {
        "XDG_DESKTOP_DIR": "Desktop",
        "XDG_DOWNLOAD_DIR": "Downloads",
        "XDG_DOCUMENTS_DIR": "Documents",
        "XDG_MUSIC_DIR": "Music",
        "XDG_PICTURES_DIR": "Pictures",
        "XDG_VIDEOS_DIR": "Videos",
    }
    if USER_DIRS_PATH.exists():
        for line in USER_DIRS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').replace("$HOME", str(HOME))
            if k in key_map:
                mapping[key_map[k]] = Path(v)
    return {k: p.resolve() for k, p in mapping.items()}


def parse_iso_timestamp(ts: str) -> datetime.datetime | None:
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_excluded(folder: Path, pinned_realpaths: set[Path], config: dict) -> bool:
    try:
        real = folder.resolve()
    except OSError:
        return True

    if real in pinned_realpaths or real == HOME.resolve():
        return True

    real_str = str(real)
    for prefix in config.get("exclude_prefixes", []):
        if real_str == prefix or real_str.startswith(prefix.rstrip("/") + "/"):
            return True

    exclude_names = set(config.get("exclude_names", []))
    for part in real.parts:
        if part in exclude_names or (part.startswith(".") and part != "/"):
            return True

    return False


def collect_xbel_scores(xbel_path: Path, half_life_days: float) -> dict[Path, float]:
    scores: dict[Path, float] = {}
    if not xbel_path.exists():
        return scores

    try:
        tree = ET.parse(xbel_path)
    except ET.ParseError as exc:
        print(f"Warning: Could not parse {xbel_path}: {exc}", file=sys.stderr)
        return scores

    now = datetime.datetime.now(datetime.timezone.utc)
    ns = {"bookmark": "http://www.freedesktop.org/standards/desktop-bookmarks"}

    for bm in tree.getroot().findall("bookmark"):
        href = bm.attrib.get("href", "")
        if not href.startswith("file://"):
            continue
        parsed = urllib.parse.urlparse(href)
        raw_path = Path(urllib.parse.unquote(parsed.path))

        folder = raw_path if raw_path.is_dir() else raw_path.parent
        if not folder.is_dir():
            continue

        visited_str = bm.attrib.get("visited") or bm.attrib.get("modified") or bm.attrib.get("added")
        dt = parse_iso_timestamp(visited_str)
        age_days = max(0.0, (now - dt).total_seconds() / 86400.0) if dt else 14.0
        decay = math.pow(0.5, age_days / max(0.1, half_life_days))

        total_count = 0
        cosmic_bonus = 1.0
        for app in bm.findall(".//bookmark:application", ns):
            try:
                c = int(app.attrib.get("count", "1"))
            except ValueError:
                c = 1
            total_count += max(1, c)
            if "CosmicFiles" in app.attrib.get("name", "") or "cosmic-files" in app.attrib.get("exec", ""):
                cosmic_bonus = 1.5

        total_count = max(1, total_count)
        folder_real = folder.resolve()
        scores[folder_real] = scores.get(folder_real, 0.0) + (total_count * cosmic_bonus * decay)

    return scores


def collect_zoxide_scores() -> dict[Path, float]:
    scores: dict[Path, float] = {}
    if not shutil.which("zoxide"):
        return scores
    try:
        res = subprocess.run(
            ["zoxide", "query", "-l", "-s"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if res.returncode != 0:
            return scores
        for line in res.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            raw_score, raw_path = float(parts[0]), Path(parts[1])
            if raw_path.is_dir():
                scores[raw_path.resolve()] = math.log1p(max(0.0, raw_score))
    except Exception:
        pass
    return scores


def rank_dynamic_folders(config: dict, xbel_path: Path = XBEL_PATH) -> list[tuple[Path, float]]:
    xdg_map = resolve_xdg_dirs()
    pinned_realpaths: set[Path] = set()
    for item in config.get("pinned", []):
        if item in xdg_map:
            pinned_realpaths.add(xdg_map[item])
        else:
            p = Path(item).expanduser()
            try:
                pinned_realpaths.add(p.resolve())
            except OSError:
                pass

    half_life = float(config.get("half_life_days", 7.0))
    combined: dict[Path, float] = {}

    for path, sc in collect_xbel_scores(xbel_path, half_life).items():
        if not is_excluded(path, pinned_realpaths, config):
            combined[path] = combined.get(path, 0.0) + sc

    if config.get("use_zoxide", True):
        for path, sc in collect_zoxide_scores().items():
            if not is_excluded(path, pinned_realpaths, config):
                combined[path] = combined.get(path, 0.0) + sc

    ranked = sorted(combined.items(), key=lambda kv: (-kv[1], str(kv[0])))
    max_dyn = int(config.get("max_dynamic", 4))
    return ranked[:max_dyn]


def format_ron_favorites(pinned: list[str], dynamic_paths: list[Path]) -> str:
    lines = ["["]
    seen_paths: set[str] = set()

    for item in pinned:
        if item in COSMIC_ENUMS:
            lines.append(f"    {item},")
        else:
            p_str = str(Path(item).expanduser())
            if p_str not in seen_paths:
                seen_paths.add(p_str)
                escaped = p_str.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'    Path("{escaped}"),')

    for p in dynamic_paths:
        p_str = str(p)
        if p_str not in seen_paths:
            seen_paths.add(p_str)
            escaped = p_str.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'    Path("{escaped}"),')

    lines.append("]")
    return "\n".join(lines) + "\n"


def atomic_write_if_changed(target: Path, content: str) -> bool:
    if target.exists():
        try:
            current = target.read_text(encoding="utf-8")
            if current.strip() == content.strip():
                return False
        except OSError:
            pass

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".favorites.", dir=str(target.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return True


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        d1 = tmp / "WorkProject"
        d2 = tmp / "Photos2026"
        d_pinned = tmp / "PinnedDir"
        d_hidden = tmp / ".secret"
        for d in (d1, d2, d_pinned, d_hidden):
            d.mkdir()

        xbel = tmp / "recently-used.xbel"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        xbel.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks">
  <bookmark href="file://{d1}/main.py" visited="{now_iso}">
    <info><metadata><bookmark:applications>
      <bookmark:application name="com.system76.CosmicFiles" exec="cosmic-files" count="5"/>
    </bookmark:applications></metadata></info>
  </bookmark>
  <bookmark href="file://{d2}/img.png" visited="{now_iso}">
    <info><metadata><bookmark:applications>
      <bookmark:application name="Viewer" exec="viewer" count="2"/>
    </bookmark:applications></metadata></info>
  </bookmark>
  <bookmark href="file://{d_pinned}/doc.txt" visited="{now_iso}">
    <info><metadata><bookmark:applications>
      <bookmark:application name="Editor" exec="ed" count="10"/>
    </bookmark:applications></metadata></info>
  </bookmark>
  <bookmark href="file://{d_hidden}/key.pem" visited="{now_iso}">
    <info><metadata><bookmark:applications>
      <bookmark:application name="Editor" exec="ed" count="20"/>
    </bookmark:applications></metadata></info>
  </bookmark>
</xbel>""",
            encoding="utf-8",
        )

        cfg = {
            "pinned": ["Home", str(d_pinned)],
            "last_dynamic": [],
            "max_dynamic": 3,
            "half_life_days": 7.0,
            "use_zoxide": False,
            "sync_gui_favorites": True,
            "exclude_prefixes": [],
            "exclude_names": [],
        }
        ranked = rank_dynamic_folders(cfg, xbel_path=xbel)
        ranked_paths = [p for p, _ in ranked]
        assert ranked_paths == [d1.resolve(), d2.resolve()], f"Unexpected ranking: {ranked_paths}"

        ron = format_ron_favorites(cfg["pinned"], ranked_paths)
        parsed = parse_ron_favorites(ron)
        assert parsed == ["Home", str(d_pinned), str(d1.resolve()), str(d2.resolve())], f"Parse mismatch: {parsed}"
        assert ".secret" not in ron

        fav_target = tmp / "favorites"
        assert atomic_write_if_changed(fav_target, ron) is True
        assert atomic_write_if_changed(fav_target, ron) is False
    print("Self-test passed successfully.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dynamically sync most frequent folders into COSMIC Files sidebar favorites."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print ranked folders and generated RON without saving.")
    parser.add_argument("--pin", metavar="PATH", help="Add a folder path to the permanent pinned list.")
    parser.add_argument("--unpin", metavar="PATH", help="Remove a folder path from the permanent pinned list.")
    parser.add_argument("--test", action="store_true", help="Run internal self-test.")
    args = parser.parse_args()

    if args.test:
        run_self_test()
        return 0

    config = load_config()
    sync_gui_pins(config)

    if args.pin:
        p = str(Path(args.pin).expanduser().resolve()) if args.pin not in COSMIC_ENUMS else args.pin
        if p not in config["pinned"]:
            config["pinned"].append(p)
            print(f"Pinned: {p}")
        else:
            print(f"Already pinned: {p}")

    if args.unpin:
        target_raw = args.unpin
        target_res = str(Path(target_raw).expanduser().resolve()) if target_raw not in COSMIC_ENUMS else target_raw
        before = len(config["pinned"])
        config["pinned"] = [x for x in config["pinned"] if x not in (target_raw, target_res)]
        if len(config["pinned"]) < before:
            print(f"Unpinned: {target_raw}")
        else:
            print(f"Not found in pinned list: {target_raw}")

    ranked = rank_dynamic_folders(config)
    dynamic_paths = [p for p, _ in ranked]
    ron_output = format_ron_favorites(config.get("pinned", []), dynamic_paths)

    if args.dry_run:
        print("=== Pinned Favorites ===")
        for item in config.get("pinned", []):
            print(f"  [PIN] {item}")
        print("\n=== Top Dynamic Frequent Folders ===")
        for p, score in ranked:
            print(f"  [{score:6.2f}] {p}")
        print("\n=== Generated COSMIC RON ===")
        print(ron_output, end="")
        return 0

    config["last_dynamic"] = [str(p) for p in dynamic_paths]
    save_config(config)

    changed = atomic_write_if_changed(COSMIC_FAVORITES, ron_output)
    if changed:
        print(f"Updated {COSMIC_FAVORITES} with {len(dynamic_paths)} dynamic folder(s).")
    else:
        print("COSMIC favorites already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
