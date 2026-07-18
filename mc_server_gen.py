#!/usr/bin/env python3
"""
Minecraft Java Edition Single-Player World Generator (server-jar method)

For each seed, this:
  1. (once) downloads the official server jar for the target version,
  2. writes server.properties with your categorical settings + the seed,
  3. runs the server headless just long enough to generate the spawn area,
  4. copies the generated world into your singleplayer saves folder,
  5. post-edits level.dat for settings not exposed in server.properties
     (e.g. keepInventory, cheats/allowCommands).

Because Minecraft itself writes level.dat, the worlds are always valid for
whatever version's jar you generate them with.

Requires: nbtlib   (pip install nbtlib)
          Java      (25+ for MC 26.x); the script uses whatever `java` is on PATH.
"""

import os
import sys
import io
import re
import gzip
import json
import time
import shutil
import hashlib
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import nbtlib
    from nbtlib import String, Byte
except ImportError:
    print("ERROR: nbtlib not found. Install it with:  pip install nbtlib")
    sys.exit(1)

VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
NAME_PREFIX = "Dappled"


# ---------------------------------------------------------------------------
# Settings shared by every generated world
# ---------------------------------------------------------------------------
MINECRAFT_VERSION = "26.2"

# Leave "" to auto-detect Java (checks PATH + Minecraft's bundled runtime).
# If auto-detection fails, paste the full path to java.exe here, e.g.:
#   JAVA_PATH = r"C:\Users\you\AppData\Roaming\.minecraft\runtime\...\bin\java.exe"
JAVA_PATH = ""

SETTINGS = {
    "gamemode": 0,                   # 0=Survival, 1=Creative, 2=Adventure, 3=Spectator
    "difficulty": 0,                 # 0=Peaceful, 1=Easy, 2=Normal, 3=Hard
    "hardcore": 0,                   # 0=False, 1=True
    "pvp": 1,                        # 0=False, 1=True
    "spawn_monsters": 1,             # 0=False, 1=True
    "spawn_animals": 1,              # 0=False, 1=True
    "spawn_npcs": 1,                 # 0=False, 1=True
    "generate_structures": 1,        # 0=False, 1=True
    "allow_commands": 0,             # cheats in singleplayer. 0=False, 1=True
    "retain_inventory_on_death": 0,  # keepInventory gamerule. 0=drop, 1=keep
}

_GAMEMODE = {0: "survival", 1: "creative", 2: "adventure", 3: "spectator"}
_DIFFICULTY = {0: "peaceful", 1: "easy", 2: "normal", 3: "hard"}


def _bool(v) -> str:
    return "true" if v else "false"


# ---------------------------------------------------------------------------
# Locate a usable Java (Minecraft ships its own; PATH often has none)
# ---------------------------------------------------------------------------
def required_java_major(version: str) -> int:
    """Minimum Java major version needed to run a given Minecraft version."""
    # Calendar versions (26.x, ...) need Java 25; 1.20.5+/1.21+ need 21; older 17.
    if re.match(r"^\d{2}\.", version):        # e.g. "26.2"
        return 25
    if version.startswith("1.21"):
        return 21
    if version.startswith("1.20"):
        # 1.20.5 and 1.20.6 need 21; earlier 1.20.x need 17
        parts = version.split(".")
        if len(parts) >= 3 and int(parts[2]) >= 5:
            return 21
        return 17
    return 17


def _java_major(java_exe) -> int:
    try:
        out = subprocess.run([str(java_exe), "-version"],
                             capture_output=True, text=True, timeout=15)
        text = (out.stderr or "") + (out.stdout or "")
        m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
        if not m:
            return -1
        major = int(m.group(1))
        if major == 1 and m.group(2):     # old 1.x scheme (1.8 == Java 8)
            major = int(m.group(2))
        return major
    except Exception:
        return -1


def _candidate_java_paths() -> List[Path]:
    exe = "java.exe" if sys.platform == "win32" else "java"
    roots: List[Path] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")
        if appdata:
            roots.append(Path(appdata) / ".minecraft" / "runtime")
        roots.append(Path(r"C:\Program Files (x86)\Minecraft Launcher\runtime"))
        if local:
            roots.append(Path(local) / "Packages" /
                         "Microsoft.4297127D64EC6_8wekyb3d8bbwe" /
                         "LocalCache" / "Local" / "runtime")
    elif sys.platform == "darwin":
        roots.append(Path.home() / "Library" / "Application Support" /
                     "minecraft" / "runtime")
    else:
        roots.append(Path.home() / ".minecraft" / "runtime")

    found: List[Path] = []
    for root in roots:
        if root.is_dir():
            found.extend(root.rglob(exe))
    return found


def find_java(override: str = "") -> Tuple[Optional[str], int]:
    """Return (path_to_java, major_version) for the newest Java available."""
    candidates: List[Path] = []
    if override:
        candidates.append(Path(override))
    onpath = shutil.which("java")
    if onpath:
        candidates.append(Path(onpath))
    candidates.extend(_candidate_java_paths())

    best: Tuple[Optional[str], int] = (None, -1)
    for c in candidates:
        try:
            if not c or not Path(c).exists():
                continue
        except OSError:
            continue
        major = _java_major(c)
        if major > best[1]:
            best = (str(c), major)
    return best


# ---------------------------------------------------------------------------
# Locate the singleplayer saves directory
# ---------------------------------------------------------------------------
def default_saves_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / ".minecraft" / "saves"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "minecraft" / "saves"
    else:
        return Path.home() / ".minecraft" / "saves"


# ---------------------------------------------------------------------------
# Download the server jar via the official version manifest
# ---------------------------------------------------------------------------
def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_server_download(version: str) -> dict:
    """Return {'url':..., 'sha1':..., 'size':...} for the server jar."""
    manifest = _get_json(VERSION_MANIFEST)
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        raise RuntimeError(
            f"Version '{version}' not found in the manifest. "
            f"Check the version string."
        )
    version_json = _get_json(entry["url"])
    downloads = version_json.get("downloads", {})
    if "server" not in downloads:
        raise RuntimeError(f"No server jar published for version '{version}'.")
    return downloads["server"]


def download_server_jar(version: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = resolve_server_download(version)

    # Skip re-download if present and hash matches
    if dest.exists() and _sha1(dest) == info.get("sha1"):
        print(f"  Server jar already present and verified: {dest.name}")
        return dest

    print(f"  Downloading server jar for {version} "
          f"({info['size'] / 1e6:.1f} MB)...")
    with urllib.request.urlopen(info["url"], timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)

    got = _sha1(dest)
    if got != info.get("sha1"):
        raise RuntimeError(
            f"SHA1 mismatch on downloaded jar (expected {info.get('sha1')}, got {got})."
        )
    print("  Download verified.")
    return dest


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# server.properties + eula.txt
# ---------------------------------------------------------------------------
def write_eula(server_dir: Path):
    # By writing this you (the user) accept Mojang's EULA: https://aka.ms/MinecraftEULA
    (server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")


def write_server_properties(server_dir: Path, seed: int):
    s = SETTINGS
    props = {
        "level-name": "world",
        "level-seed": str(seed),
        "gamemode": _GAMEMODE[s["gamemode"]],
        "difficulty": _DIFFICULTY[s["difficulty"]],
        "hardcore": _bool(s["hardcore"]),
        "pvp": _bool(s["pvp"]),
        "spawn-monsters": _bool(s["spawn_monsters"]),
        "spawn-animals": _bool(s["spawn_animals"]),
        "spawn-npcs": _bool(s["spawn_npcs"]),
        "generate-structures": _bool(s["generate_structures"]),
        "online-mode": "false",     # no auth needed for local generation
        "max-players": "1",
        "view-distance": "10",
        "sync-chunk-writes": "true",
        "white-list": "false",
        "spawn-protection": "0",
    }
    text = "".join(f"{k}={v}\n" for k, v in props.items())
    (server_dir / "server.properties").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Run the server long enough to generate, then stop it cleanly
# ---------------------------------------------------------------------------
def run_server_generate(server_dir: Path, jar: Path,
                        java: str = "java", timeout: int = 300) -> None:
    """Boot the server, wait for 'Done', send 'stop', wait for clean exit."""
    cmd = [java, "-Xmx2G", "-jar", str(jar), "--nogui"]
    proc = subprocess.Popen(
        cmd, cwd=str(server_dir),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )

    start = time.time()
    done_seen = False
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            # Uncomment to see full server output:
            # print("   [server]", line)
            if ("Done (" in line and "For help" in line) and not done_seen:
                done_seen = True
                proc.stdin.write("stop\n")
                proc.stdin.flush()
            if time.time() - start > timeout:
                raise TimeoutError("Server generation timed out.")
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()

    if not done_seen:
        raise RuntimeError(
            "Server exited before finishing generation. "
            "Check that your Java version is new enough for this Minecraft version."
        )


# ---------------------------------------------------------------------------
# Post-edit the (now valid) level.dat for settings not in server.properties
# ---------------------------------------------------------------------------
def post_edit_level_dat(world_dir: Path):
    s = SETTINGS
    level = world_dir / "level.dat"
    nbt = nbtlib.load(level)          # auto-detects gzip
    data = nbt["Data"]

    data.setdefault("GameRules", nbtlib.Compound())
    data["GameRules"]["keepInventory"] = String(
        "true" if s["retain_inventory_on_death"] else "false"
    )
    # allowCommands = cheats in singleplayer
    data["allowCommands"] = Byte(1 if s["allow_commands"] else 0)

    nbt.save(str(level), gzipped=True)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def generate_world(seed: int, world_name: str, server_dir: Path,
                   jar: Path, saves_dir: Path, java: str = "java") -> None:
    # Fresh world each run
    world_src = server_dir / "world"
    if world_src.exists():
        shutil.rmtree(world_src)

    write_server_properties(server_dir, seed)
    run_server_generate(server_dir, jar, java=java)

    if not (world_src / "level.dat").exists():
        raise RuntimeError("Generation finished but no level.dat was produced.")

    post_edit_level_dat(world_src)

    dest = saves_dir / world_name
    if dest.exists():
        print(f"  '{world_name}' already exists in saves, skipping copy.")
        return
    shutil.copytree(world_src, dest)
    print(f"  Placed world: {world_name}  (seed: {seed})")


def load_seeds_from_file(filepath: str) -> List[int]:
    seeds = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    seeds.append(int(line))
                except ValueError:
                    print(f"  Warning: invalid seed '{line}', skipping.")
    return seeds


def main():
    global NAME_PREFIX
    saves_dir = default_saves_dir()
    if not saves_dir.exists():
        print(f"ERROR: saves folder not found at {saves_dir}")
        print("Run Minecraft at least once so the folder exists, or edit default_saves_dir().")
        sys.exit(1)

    work = Path.home() / ".mc_world_gen"
    server_dir = work / "server"
    server_dir.mkdir(parents=True, exist_ok=True)
    jar = server_dir / f"server-{MINECRAFT_VERSION}.jar"

    print("=" * 60)
    print(f"Minecraft World Generator (server method) - {MINECRAFT_VERSION}")
    print("=" * 60)

    # Locate Java before doing anything expensive
    need = required_java_major(MINECRAFT_VERSION)
    java, major = find_java(JAVA_PATH)
    if java is None:
        print("ERROR: No Java found on PATH or in Minecraft's runtime folder.")
        print(f"Minecraft {MINECRAFT_VERSION} needs Java {need}+.")
        print("Set JAVA_PATH at the top of this script to your java.exe.")
        sys.exit(1)
    if major < need:
        print(f"ERROR: Found Java {major} at {java}, but Minecraft "
              f"{MINECRAFT_VERSION} needs Java {need}+.")
        print("Install a newer Java, or set JAVA_PATH to a newer java.exe.")
        print("Tip: Minecraft's own runtime lives under "
              r"%APPDATA%\.minecraft\runtime\ once you've launched that version.")
        sys.exit(1)
    print(f"Using Java {major}: {java}")

    download_server_jar(MINECRAFT_VERSION, jar)
    write_eula(server_dir)   # writes eula=true (accepts Mojang EULA)

    seeds = load_seeds_from_file("seeds.txt") if os.path.exists("seeds.txt") \
        else [12345, 67890, -999999]

    ok = 0
    for i, seed in enumerate(seeds, 1):
        name = f"{NAME_PREFIX}_{i}_{seed}"
        print(f"\n[{i}/{len(seeds)}] Generating {name} ...")
        try:
            generate_world(seed, name, server_dir, jar, saves_dir, java=java)
            ok += 1
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\n" + "=" * 60)
    print(f"Done. {ok}/{len(seeds)} worlds created in {saves_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
