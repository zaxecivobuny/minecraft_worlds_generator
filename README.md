# Minecraft Worlds Generator

Automatically generate Minecraft Java Edition single-player worlds from a list of seeds with predefined categorical settings.

## Setup

1. Install Python 3.7+
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Quick Start

1. Edit `seeds.txt` and add your seeds (one per line)
2. Configure settings in `minecraft_world_generator.py` (top of file, `SETTINGS` dict)
3. Run:
   ```
   python minecraft_world_generator.py
   ```

### Configuration

Open `minecraft_world_generator.py` and modify the `SETTINGS` dictionary:

```python
SETTINGS = {
    "gamemode": 0,                      # 0=Survival, 1=Creative, 2=Adventure, 3=Spectator
    "difficulty": 2,                    # 0=Peaceful, 1=Easy, 2=Normal, 3=Hard
    "allow_commands": 1,                # Enable/disable command blocks
    "pvp": 1,                           # Enable/disable PvP
    "spawn_mobs": 1,                    # Mobs spawn or not
    "spawn_animals": 1,                 # Animals spawn or not
    "spawn_npc": 1,                     # NPCs spawn or not
    "hardcore": 0,                      # Hardcore mode
    "retain_inventory_on_death": 0,     # 0=drop on death, 1=keep inventory
    "structures": 1,                    # Generate structures (temples, strongholds, etc)
    "water_lake_chance": 1,             # Water lake generation frequency (1-100)
    "lava_lake_chance": 2,              # Lava lake generation frequency (1-100)
    "dungeon_chance": 1,                # Dungeon generation frequency (1-100)
}
```

### Seed Input Methods

**Method 1: seeds.txt file** (recommended)
```
# seeds.txt
12345
67890
-999999
# This is a comment
999999
```

Then uncomment this line in the script:
```python
seeds = load_seeds_from_file("seeds.txt")
```

**Method 2: Hardcoded list**
Edit the bottom of the script:
```python
seeds = [12345, 67890, -999999, 999999]
```

## Output

Worlds are created in your Minecraft saves directory (typically `%APPDATA%\.minecraft\saves` on Windows).

World names follow the pattern: `WorldName_1_seed`, `WorldName_2_seed`, etc.

## Notes

- Worlds won't have pre-generated chunks until you load them in Minecraft
- Existing worlds are automatically skipped
- Version ID in the script matches Minecraft 1.20.1 — update if you use a different version
- Comments in seeds.txt (lines starting with `#`) are ignored
