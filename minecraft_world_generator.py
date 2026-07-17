#!/usr/bin/env python3
"""
Minecraft Java Edition Single-Player World Generator
Automatically creates worlds from a list of seeds with predefined categorical settings.
"""

import os
import sys
import struct
import gzip
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import subprocess
import io

# No external dependencies needed - using manual NBT binary encoding


class MinecraftWorldGenerator:
    """Generate Minecraft Java Edition worlds from seeds with fixed settings."""
    
    # Categorical settings - modify these for your worlds
    SETTINGS = {
        "gamemode": 0,              # 0=Survival, 1=Creative, 2=Adventure, 3=Spectator
        "difficulty": 2,             # 0=Peaceful, 1=Easy, 2=Normal, 3=Hard
        "allow_commands": 1,         # 0=False, 1=True
        "pvp": 1,                    # 0=False, 1=True
        "spawn_mobs": 1,             # 0=False, 1=True
        "spawn_animals": 1,          # 0=False, 1=True
        "spawn_npc": 1,              # 0=False, 1=True
        "hardcore": 0,               # 0=False, 1=True
        "retain_inventory_on_death": 0,  # 0=False (drop on death), 1=True (keep inventory)
        "structures": 1,             # 0=False, 1=True (temples, strongholds, etc)
        "water_lake_chance": 1,      # 1-100, water lake generation frequency
        "lava_lake_chance": 2,       # 1-100, lava lake generation frequency
        "dungeon_chance": 1,         # 1-100, dungeon generation frequency
    }
    
    def __init__(self, minecraft_dir: str = None):
        """
        Initialize the generator.
        
        Args:
            minecraft_dir: Path to .minecraft directory. If None, uses default Windows/Unix location
        """
        if minecraft_dir is None:
            # Windows: C:\Users\<username>\AppData\Roaming\.minecraft
            # Unix/Linux: ~/.minecraft
            if sys.platform == "win32":
                minecraft_dir = os.path.expanduser("~\\AppData\\Roaming\\.minecraft")
            else:
                minecraft_dir = os.path.expanduser("~/.minecraft")
        
        self.minecraft_dir = Path(minecraft_dir)
        self.saves_dir = self.minecraft_dir / "saves"
        
        if not self.saves_dir.exists():
            print(f"ERROR: {self.saves_dir} not found.")
            print(f"Expected Minecraft at: {self.minecraft_dir}")
            print(f"Is Minecraft installed? Check your .minecraft location.")
            sys.exit(1)
    
    def _write_nbt_tag(self, name: str, value: Any) -> bytes:
        """Manually encode a single NBT tag to bytes."""
        buf = io.BytesIO()
        
        if isinstance(value, dict):
            # TAG_Compound
            buf.write(b'\x0a')  # Tag type 10 = Compound
            self._write_string(buf, name)
            for k, v in value.items():
                buf.write(self._write_nbt_tag(k, v))
            buf.write(b'\x00')  # End tag
        elif isinstance(value, str):
            # TAG_String
            buf.write(b'\x08')  # Tag type 8 = String
            self._write_string(buf, name)
            self._write_string(buf, value)
        elif isinstance(value, int):
            # TAG_Long or TAG_Int (use Long for large values)
            buf.write(b'\x04')  # Tag type 4 = Int
            self._write_string(buf, name)
            buf.write(struct.pack('>i', value))
        
        return buf.getvalue()
    
    def _write_string(self, buf: io.BytesIO, s: str):
        """Write a UTF-8 string with 2-byte length prefix."""
        encoded = s.encode('utf-8')
        buf.write(struct.pack('>H', len(encoded)))
        buf.write(encoded)
    
    def create_level_dat(self, seed: int, world_name: str) -> bytes:
        """
        Create a level.dat file (NBT format) for the given seed.
        
        Args:
            seed: Minecraft world seed (int)
            world_name: Name of the world
            
        Returns:
            Gzipped NBT data as bytes
        """
        buf = io.BytesIO()
        
        # TAG_Compound (root)
        buf.write(b'\x0a')  # Tag type 10 = Compound
        self._write_string(buf, "")  # Root name is empty
        
        # Data compound
        buf.write(b'\x0a')  # Compound tag
        self._write_string(buf, "Data")
        
        # Write individual tags
        buf.write(b'\x03')  # TAG_Int
        self._write_string(buf, "GameType")
        buf.write(struct.pack('>i', self.SETTINGS["gamemode"]))
        
        buf.write(b'\x01')  # TAG_Byte
        self._write_string(buf, "Difficulty")
        buf.write(struct.pack('B', self.SETTINGS["difficulty"]))
        
        buf.write(b'\x01')  # TAG_Byte
        self._write_string(buf, "Hardcore")
        buf.write(struct.pack('B', self.SETTINGS["hardcore"]))
        
        buf.write(b'\x08')  # TAG_String
        self._write_string(buf, "LevelName")
        self._write_string(buf, world_name)
        
        buf.write(b'\x04')  # TAG_Long (seed as int for now)
        self._write_string(buf, "Seed")
        buf.write(struct.pack('>q', seed))  # 8-byte long
        
        buf.write(b'\x04')  # TAG_Long
        self._write_string(buf, "Time")
        buf.write(struct.pack('>q', 0))
        
        buf.write(b'\x04')  # TAG_Long
        self._write_string(buf, "DayTime")
        buf.write(struct.pack('>q', 0))
        
        buf.write(b'\x04')  # TAG_Long
        self._write_string(buf, "LastPlayed")
        buf.write(struct.pack('>q', int(datetime.now().timestamp() * 1000)))
        
        buf.write(b'\x03')  # TAG_Int
        self._write_string(buf, "SpawnX")
        buf.write(struct.pack('>i', 0))
        
        buf.write(b'\x03')  # TAG_Int
        self._write_string(buf, "SpawnY")
        buf.write(struct.pack('>i', 64))
        
        buf.write(b'\x03')  # TAG_Int
        self._write_string(buf, "SpawnZ")
        buf.write(struct.pack('>i', 0))
        
        # GameRules compound
        buf.write(b'\x0a')  # Compound
        self._write_string(buf, "GameRules")
        
        # Write game rules
        rules = {
            "keepInventory": "1" if self.SETTINGS["retain_inventory_on_death"] else "0",
            "doMobSpawning": "1" if self.SETTINGS["spawn_mobs"] else "0",
            "pvp": "1" if self.SETTINGS["pvp"] else "0",
        }
        
        for rule_name, rule_value in rules.items():
            buf.write(b'\x08')  # TAG_String
            self._write_string(buf, rule_name)
            self._write_string(buf, rule_value)
        
        buf.write(b'\x00')  # End tag for GameRules
        
        # Version compound
        buf.write(b'\x0a')  # Compound
        self._write_string(buf, "Version")
        
        buf.write(b'\x03')  # TAG_Int
        self._write_string(buf, "Id")
        buf.write(struct.pack('>i', 3107))
        
        buf.write(b'\x08')  # TAG_String
        self._write_string(buf, "Name")
        self._write_string(buf, "1.20.1")
        
        buf.write(b'\x00')  # End tag for Version
        
        buf.write(b'\x00')  # End tag for Data
        
        # Gzip compress
        compressed = io.BytesIO()
        with gzip.GzipFile(fileobj=compressed, mode='wb') as gz:
            gz.write(buf.getvalue())
        
        return compressed.getvalue()
    
    def create_world(self, seed: int, world_name: str = None) -> Path:
        """
        Create a new world directory with level.dat.
        
        Args:
            seed: Minecraft world seed
            world_name: Name of the world. If None, uses seed as name.
            
        Returns:
            Path to the created world directory
        """
        if world_name is None:
            world_name = f"World_{seed}"
        
        world_path = self.saves_dir / world_name
        
        # Check if world already exists
        if world_path.exists():
            print(f"⚠️  World '{world_name}' already exists, skipping...")
            return world_path
        
        # Create world directory
        world_path.mkdir(parents=True, exist_ok=True)
        
        # Create level.dat
        level_dat_path = world_path / "level.dat"
        level_dat_bytes = self.create_level_dat(seed, world_name)
        with open(level_dat_path, 'wb') as f:
            f.write(level_dat_bytes)
        
        # Create empty datapacks directory
        datapacks_dir = world_path / "datapacks"
        datapacks_dir.mkdir(exist_ok=True)
        
        print(f"✓ Created world: {world_name} (Seed: {seed})")
        return world_path
    
    def generate_worlds(self, seeds: List[int], world_name_prefix: str = "World"):
        """
        Generate multiple worlds from a list of seeds.
        
        Args:
            seeds: List of seed integers
            world_name_prefix: Prefix for world names
        """
        print(f"\n{'='*60}")
        print(f"Minecraft World Generator (Java Edition)")
        print(f"{'='*60}")
        print(f"Settings:")
        for key, value in self.SETTINGS.items():
            print(f"  {key}: {value}")
        print(f"{'='*60}\n")
        
        successful = 0
        skipped = 0
        
        for i, seed in enumerate(seeds, 1):
            try:
                world_name = f"{world_name_prefix}_{i}_{seed}"
                self.create_world(seed, world_name)
                successful += 1
            except Exception as e:
                print(f"✗ Failed to create world from seed {seed}: {e}")
        
        print(f"\n{'='*60}")
        print(f"Complete! Created {successful}/{len(seeds)} worlds")
        print(f"Worlds saved to: {self.saves_dir}")
        print(f"{'='*60}\n")


def load_seeds_from_file(filepath: str) -> List[int]:
    """Load seeds from a file (one per line)."""
    seeds = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):  # Skip empty lines and comments
                try:
                    seeds.append(int(line))
                except ValueError:
                    print(f"Warning: Invalid seed '{line}', skipping...")
    return seeds


# Example usage
if __name__ == "__main__":
    # Option 1: Hardcoded seed list
    seeds = [
        12345,
        67890,
        -999999,
        999999,
        2147483647,
    ]
    
    # Option 2: Load from file
    # seeds = load_seeds_from_file("seeds.txt")
    
    # Create generator and build worlds
    generator = MinecraftWorldGenerator()
    generator.generate_worlds(seeds, world_name_prefix="TestWorld")
