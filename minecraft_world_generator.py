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

# Try to import nbtlib; if missing, provide install instructions
try:
    from nbtlib import load, save, TAG_Compound, TAG_Long, TAG_Int, TAG_String, TAG_Byte, TAG_List, TAG_Double
    from nbtlib.tag import TAG_Byte_Array
except ImportError:
    print("ERROR: nbtlib not found. Install it with:")
    print("  pip install nbtlib")
    sys.exit(1)


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
            minecraft_dir: Path to .minecraft directory. If None, uses ~/.minecraft
        """
        if minecraft_dir is None:
            minecraft_dir = os.path.expanduser("~/.minecraft")
        
        self.minecraft_dir = Path(minecraft_dir)
        self.saves_dir = self.minecraft_dir / "saves"
        
        if not self.saves_dir.exists():
            print(f"ERROR: {self.saves_dir} not found. Is Minecraft installed?")
            sys.exit(1)
    
    def create_level_dat(self, seed: int, world_name: str) -> bytes:
        """
        Create a level.dat file (NBT format) for the given seed.
        
        Args:
            seed: Minecraft world seed (int)
            world_name: Name of the world
            
        Returns:
            Gzipped NBT data as bytes
        """
        # Build the NBT structure using nbtlib
        data = {
            "Seed": TAG_Long(seed),
            "GameType": TAG_Int(self.SETTINGS["gamemode"]),
            "Difficulty": TAG_Int(self.SETTINGS["difficulty"]),
            "DifficultyLocked": TAG_Byte(0),
            "Hardcore": TAG_Byte(self.SETTINGS["hardcore"]),
            "LevelName": TAG_String(world_name),
            "LastPlayed": TAG_Long(int(datetime.now().timestamp() * 1000)),
            "Time": TAG_Long(0),
            "DayTime": TAG_Long(0),
            "SpawnX": TAG_Int(0),
            "SpawnY": TAG_Int(64),
            "SpawnZ": TAG_Int(0),
            "GameRules": TAG_Compound({
                "commandBlockOutput": TAG_String("1"),
                "doCommandBlocks": TAG_String("1" if self.SETTINGS["allow_commands"] else "0"),
                "doDayLightCycle": TAG_String("1"),
                "doEntityDrops": TAG_String("1"),
                "doFireTick": TAG_String("1"),
                "doMobSpawning": TAG_String("1" if self.SETTINGS["spawn_mobs"] else "0"),
                "doTileDrops": TAG_String("1"),
                "keepInventory": TAG_String("1" if self.SETTINGS["retain_inventory_on_death"] else "0"),
                "logAdminCommands": TAG_String("1"),
                "mobGriefing": TAG_String("1"),
                "pvp": TAG_String("1" if self.SETTINGS["pvp"] else "0"),
                "randomTickSpeed": TAG_String("3"),
                "sendCommandFeedback": TAG_String("1"),
                "showDeathMessages": TAG_String("1"),
                "spawnAnimals": TAG_String("1" if self.SETTINGS["spawn_animals"] else "0"),
                "spawnMonsters": TAG_String("1" if self.SETTINGS["spawn_mobs"] else "0"),
                "spawnNPCs": TAG_String("1" if self.SETTINGS["spawn_npc"] else "0"),
            }),
            "Version": TAG_Compound({
                "Id": TAG_Int(3107),
                "Name": TAG_String("1.20.1"),
            }),
            "WorldGenSettings": TAG_Compound({}),
        }
        
        root = TAG_Compound({"": TAG_Compound(data)})
        
        # Save to bytes with gzip compression
        nbt_bytes = root.save(gzipped=True)
        return nbt_bytes
    
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
