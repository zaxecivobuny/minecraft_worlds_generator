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

# Try to import pynbt; if missing, provide install instructions
try:
    from nbt.nbt import NBTFile, TAG_Compound, TAG_Long, TAG_Int, TAG_String, TAG_Byte, TAG_List, TAG_Double
except ImportError:
    print("ERROR: pynbt not found. Install it with:")
    print("  pip install pynbt")
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
        root = TAG_Compound(name="")
        
        # Root tags
        data = TAG_Compound(name="Data")
        root.tags.append(data)
        
        # World seed
        data.tags.append(TAG_Long(name="Seed", value=seed))
        
        # Game rules
        game_rules = TAG_Compound(name="GameRules")
        game_rules.tags.append(TAG_String(name="commandBlockOutput", value="1"))
        game_rules.tags.append(TAG_String(name="doCommandBlocks", value="1" if self.SETTINGS["allow_commands"] else "0"))
        game_rules.tags.append(TAG_String(name="doDayLightCycle", value="1"))
        game_rules.tags.append(TAG_String(name="doEntityDrops", value="1"))
        game_rules.tags.append(TAG_String(name="doFireTick", value="1"))
        game_rules.tags.append(TAG_String(name="doMobSpawning", value="1" if self.SETTINGS["spawn_mobs"] else "0"))
        game_rules.tags.append(TAG_String(name="doTileDrops", value="1"))
        game_rules.tags.append(TAG_String(name="keepInventory", value="1" if self.SETTINGS["retain_inventory_on_death"] else "0"))
        game_rules.tags.append(TAG_String(name="logAdminCommands", value="1"))
        game_rules.tags.append(TAG_String(name="mobGriefing", value="1"))
        game_rules.tags.append(TAG_String(name="pvp", value="1" if self.SETTINGS["pvp"] else "0"))
        game_rules.tags.append(TAG_String(name="randomTickSpeed", value="3"))
        game_rules.tags.append(TAG_String(name="sendCommandFeedback", value="1"))
        game_rules.tags.append(TAG_String(name="showDeathMessages", value="1"))
        game_rules.tags.append(TAG_String(name="spawnAnimals", value="1" if self.SETTINGS["spawn_animals"] else "0"))
        game_rules.tags.append(TAG_String(name="spawnMonsters", value="1" if self.SETTINGS["spawn_mobs"] else "0"))
        game_rules.tags.append(TAG_String(name="spawnNPCs", value="1" if self.SETTINGS["spawn_npc"] else "0"))
        data.tags.append(game_rules)
        
        # World settings
        data.tags.append(TAG_Int(name="GameType", value=self.SETTINGS["gamemode"]))
        data.tags.append(TAG_Int(name="Difficulty", value=self.SETTINGS["difficulty"]))
        data.tags.append(TAG_Byte(name="DifficultyLocked", value=0))
        data.tags.append(TAG_Byte(name="Hardcore", value=self.SETTINGS["hardcore"]))
        data.tags.append(TAG_String(name="LevelName", value=world_name))
        data.tags.append(TAG_Long(name="LastPlayed", value=int(datetime.now().timestamp() * 1000)))
        data.tags.append(TAG_Long(name="Time", value=0))
        data.tags.append(TAG_Long(name="DayTime", value=0))
        
        # Spawn point
        data.tags.append(TAG_Int(name="SpawnX", value=0))
        data.tags.append(TAG_Int(name="SpawnY", value=64))
        data.tags.append(TAG_Int(name="SpawnZ", value=0))
        
        # Version info (adjust for your MC version)
        version = TAG_Compound(name="Version")
        version.tags.append(TAG_Int(name="Id", value=3107))  # Update based on your version
        version.tags.append(TAG_String(name="Name", value="1.20.1"))  # Update based on your version
        data.tags.append(version)
        
        # World generation settings
        world_gen = TAG_Compound(name="WorldGenSettings")
        
        # Noise settings (simplified)
        noise_settings = TAG_Compound(name="noise")
        world_gen.tags.append(noise_settings)
        
        data.tags.append(world_gen)
        
        # Convert to bytes
        nbt_bytes = root.save(compressed=True)
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
