# Minecraft Worlds Generator

Generate Minecraft Java Edition single-player worlds from a list of seeds, all
sharing the same predefined settings.

## Setup

```
pip install -r requirements.txt
```

## IMPORTANT: set your Minecraft version

Open `minecraft_world_generator.py` and set this line near the top of the class
to match the version you actually play:

```python
MINECRAFT_VERSION = "26.2"
```

If this is set HIGHER than your installed game, the worlds show
"Failed to load world summary" and won't open. Supported values:
1.20.x, 1.21.x, 26.1.2, 26.2 (see the DATA_VERSIONS table in the script).
(To add another, put its DataVersion in the `DATA_VERSIONS` table.)

## Usage

1. Put your seeds in `seeds.txt`, one per line (`#` starts a comment).
2. Adjust `SETTINGS` in the script if you want.
3. Run:

```
python minecraft_world_generator.py
```

Worlds are written to your saves folder (auto-detected):
- Windows: `%APPDATA%\.minecraft\saves`
- macOS: `~/Library/Application Support/minecraft/saves`
- Linux: `~/.minecraft/saves`

## Settings

```python
SETTINGS = {
    "gamemode": 0,                   # 0=Survival, 1=Creative, 2=Adventure, 3=Spectator
    "difficulty": 2,                 # 0=Peaceful, 1=Easy, 2=Normal, 3=Hard
    "allow_commands": 0,             # 0=False, 1=True
    "pvp": 1,                        # 0=False, 1=True
    "spawn_mobs": 1,                 # 0=False, 1=True
    "spawn_animals": 1,              # 0=False, 1=True
    "spawn_npc": 1,                  # 0=False, 1=True
    "hardcore": 0,                   # 0=False, 1=True
    "retain_inventory_on_death": 0,  # 0=drop on death, 1=keep inventory
    "generate_structures": 1,        # 0=False, 1=True
}
```

## Notes

- Worlds have no pre-generated terrain yet; Minecraft generates it the first
  time you open each world (normal behaviour).
- Existing world folders are skipped, not overwritten.
- If you previously ran an older, broken version of this script, delete the old
  `TestWorld_*` folders from your saves directory before regenerating.
