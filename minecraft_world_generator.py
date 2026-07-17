#!/usr/bin/env python3
"""
Minecraft Java Edition Single-Player World Generator
Automatically creates worlds from a list of seeds with predefined categorical settings.

Requires: nbtlib  (pip install nbtlib)
"""

import os
import sys
import io
import gzip
from pathlib import Path
from typing import List
from datetime import datetime

try:
    import nbtlib
    from nbtlib import File, Compound, Long, Int, Byte, String, Float
except ImportError:
    print("ERROR: nbtlib not found. Install it with:")
    print("  pip install nbtlib")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Minecraft version -> DataVersion lookup.
# The DataVersion MUST be <= your installed Minecraft version, or the world
# will show "Failed to load world summary". Set MINECRAFT_VERSION below to
# match the version you actually play.
# ---------------------------------------------------------------------------
DATA_VERSIONS = {
    "1.20":   3463,
    "1.20.1": 3465,
    "1.20.2": 3578,
    "1.20.4": 3700,
    "1.20.6": 3839,
    "1.21":   3953,
    "1.21.1": 3955,
    "1.21.4": 4189,
    "1.21.5": 4325,
    # New year.drop versioning (started 26.1, Dec 2025 scheme)
    "26.1.2": 4790,
    "26.2":   4903,
}


class MinecraftWorldGenerator:
    """Generate Minecraft Java Edition worlds from seeds with fixed settings."""

    # ---- Set this to match the Minecraft version you play ----
    MINECRAFT_VERSION = "26.2"

    # Categorical settings - modify these for your worlds
    SETTINGS = {
        "gamemode": 0,                   # 0=Survival, 1=Creative, 2=Adventure, 3=Spectator
        "difficulty": 2,                 # 0=Peaceful, 1=Easy, 2=Normal, 3=Hard
        "allow_commands": 0,             # 0=False, 1=True
        "pvp": 1,                        # 0=False, 1=True
        "spawn_mobs": 1,                 # 0=False, 1=True
        "spawn_animals": 1,              # 0=False, 1=True
        "spawn_npc": 1,                  # 0=False, 1=True
        "hardcore": 0,                   # 0=False, 1=True
        "retain_inventory_on_death": 0,  # 0=False (drop on death), 1=True (keep inventory)
        "generate_structures": 1,        # 0=False, 1=True (villages, temples, strongholds, etc)
    }

    def __init__(self, minecraft_dir: str = None):
        """
        Initialize the generator.

        Args:
            minecraft_dir: Path to .minecraft directory. If None, auto-detects
                           per-platform (AppData\\Roaming on Windows, ~ on Unix).
        """
        if minecraft_dir is None:
            if sys.platform == "win32":
                minecraft_dir = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")), ".minecraft"
                )
            elif sys.platform == "darwin":
                minecraft_dir = os.path.expanduser(
                    "~/Library/Application Support/minecraft"
                )
            else:
                minecraft_dir = os.path.expanduser("~/.minecraft")

        self.minecraft_dir = Path(minecraft_dir)
        self.saves_dir = self.minecraft_dir / "saves"

        if self.MINECRAFT_VERSION not in DATA_VERSIONS:
            print(f"ERROR: Unknown Minecraft version '{self.MINECRAFT_VERSION}'.")
            print(f"Known versions: {', '.join(DATA_VERSIONS)}")
            sys.exit(1)

        self.data_version = DATA_VERSIONS[self.MINECRAFT_VERSION]

        if not self.saves_dir.exists():
            print(f"ERROR: {self.saves_dir} not found.")
            print(f"Expected Minecraft at: {self.minecraft_dir}")
            print("Is Minecraft installed and has it been run at least once?")
            sys.exit(1)

    def create_level_dat(self, seed: int, world_name: str) -> bytes:
        """
        Build a gzipped level.dat (NBT) for the given seed.

        The structure follows the modern (1.16+) level format:
          - seed lives in Data.WorldGenSettings.seed
          - game rules are "true"/"false" strings
          - DataVersion is present in both Data.DataVersion and Data.Version.Id
        """
        s = self.SETTINGS
        now_ms = int(datetime.now().timestamp() * 1000)

        data = Compound({
            "DataVersion": Int(self.data_version),
            "version": Int(19133),                  # level format version (NOT the game version)
            "LevelName": String(world_name),
            "GameType": Int(s["gamemode"]),
            "Difficulty": Byte(s["difficulty"]),
            "DifficultyLocked": Byte(0),
            "Hardcore": Byte(s["hardcore"]),
            "allowCommands": Byte(s["allow_commands"]),
            "LastPlayed": Long(now_ms),
            "Time": Long(0),
            "DayTime": Long(0),
            "SpawnX": Int(0),
            "SpawnY": Int(64),
            "SpawnZ": Int(0),
            "SpawnAngle": Float(0.0),
            "clearWeatherTime": Int(0),
            "rainTime": Int(0),
            "thunderTime": Int(0),
            "raining": Byte(0),
            "thundering": Byte(0),
            "WanderingTraderSpawnChance": Int(25),
            "WanderingTraderSpawnDelay": Int(24000),
            "initialized": Byte(0),
            "WasModded": Byte(0),
            "GameRules": Compound({
                "keepInventory": String("true" if s["retain_inventory_on_death"] else "false"),
                "doMobSpawning": String("true" if s["spawn_mobs"] else "false"),
                "doMobLoot": String("true"),
                "doTileDrops": String("true"),
                "doEntityDrops": String("true"),
                "doFireTick": String("true"),
                "doDaylightCycle": String("true"),
                "doWeatherCycle": String("true"),
                "mobGriefing": String("true"),
                "commandBlockOutput": String("true"),
                "naturalRegeneration": String("true"),
                "pvp": String("true" if s["pvp"] else "false"),
                "showDeathMessages": String("true"),
                "sendCommandFeedback": String("true"),
                "randomTickSpeed": String("3"),
                "spawnRadius": String("10"),
            }),
            "Version": Compound({
                "Id": Int(self.data_version),
                "Name": String(self.MINECRAFT_VERSION),
                "Series": String("main"),
                "Snapshot": Byte(0),
            }),
            "WorldGenSettings": Compound({
                "seed": Long(seed),
                "generate_features": Byte(s["generate_structures"]),
                "bonus_chest": Byte(0),
                "dimensions": Compound({}),
            }),
            "DataPacks": Compound({
                "Enabled": nbtlib.List[String]([String("vanilla")]),
                "Disabled": nbtlib.List[String]([]),
            }),
        })

        nbt_file = File({"Data": data}, gzipped=True, root_name="")

        # File.write() does NOT compress on its own; gzip manually so the
        # output has the 0x1f 0x8b header Minecraft expects.
        raw = io.BytesIO()
        nbt_file.write(raw)
        out = io.BytesIO()
        with gzip.GzipFile(fileobj=out, mode="wb") as gz:
            gz.write(raw.getvalue())
        return out.getvalue()

    def create_world(self, seed: int, world_name: str = None) -> Path:
        """Create a single world folder with a valid level.dat."""
        if world_name is None:
            world_name = f"World_{seed}"

        world_path = self.saves_dir / world_name

        if world_path.exists():
            print(f"  World '{world_name}' already exists, skipping...")
            return world_path

        world_path.mkdir(parents=True, exist_ok=True)

        (world_path / "level.dat").write_bytes(
            self.create_level_dat(seed, world_name)
        )
        (world_path / "datapacks").mkdir(exist_ok=True)

        print(f"  Created: {world_name}  (seed: {seed})")
        return world_path

    def generate_worlds(self, seeds: List[int], world_name_prefix: str = "World"):
        """Create one world per seed."""
        print("=" * 60)
        print("Minecraft World Generator (Java Edition)")
        print(f"Target version: {self.MINECRAFT_VERSION}  (DataVersion {self.data_version})")
        print("=" * 60)
        for key, value in self.SETTINGS.items():
            print(f"  {key}: {value}")
        print("=" * 60)

        created = 0
        for i, seed in enumerate(seeds, 1):
            try:
                self.create_world(seed, f"{world_name_prefix}_{i}_{seed}")
                created += 1
            except Exception as e:
                print(f"  FAILED seed {seed}: {e}")

        print("=" * 60)
        print(f"Done. {created}/{len(seeds)} worlds written to:")
        print(f"  {self.saves_dir}")
        print("=" * 60)


def load_seeds_from_file(filepath: str) -> List[int]:
    """Load seeds from a text file, one per line. '#' lines are comments."""
    seeds = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    seeds.append(int(line))
                except ValueError:
                    print(f"Warning: invalid seed '{line}', skipping.")
    return seeds


if __name__ == "__main__":
    # Option 1: load from seeds.txt (recommended)
    if os.path.exists("seeds.txt"):
        seeds = load_seeds_from_file("seeds.txt")
    else:
        # Option 2: hardcoded fallback
        seeds = [12345, 67890, -999999, 999999, 2147483647]

    generator = MinecraftWorldGenerator()
    generator.generate_worlds(seeds, world_name_prefix="TestWorld")
