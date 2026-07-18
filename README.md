# Minecraft Worlds Generator (server method)

Generates valid Minecraft Java Edition single-player worlds from a list of
seeds, all sharing the same settings. Minecraft's own server writes each world,
so they always load on the version you generate with (no hand-built NBT).

## Requirements

- Python 3.8+ and `nbtlib`:  `pip install -r requirements.txt`
- Java on your PATH, new enough for your Minecraft version (26.x needs Java 25).
  Check with:  `java -version`

## Usage

1. Put your seeds in `seeds.txt`, one per line (`#` = comment).
2. Set the version + settings at the top of `mc_server_gen.py`:
   - `MINECRAFT_VERSION = "26.2"`
   - the `SETTINGS` dict (gamemode, difficulty, keepInventory, etc.)
3. Run:  `python mc_server_gen.py`

Worlds are written to your saves folder (auto-detected):
- Windows: `%APPDATA%\.minecraft\saves`
- macOS: `~/Library/Application Support/minecraft/saves`
- Linux: `~/.minecraft/saves`

## How it works

For each seed the script writes a `server.properties`, runs the server headless
until the spawn area is generated, stops it, then copies the finished `world`
folder into your saves as `World_<n>_<seed>`. Settings that server.properties
doesn't cover (keepInventory, cheats) are applied by editing the finished
`level.dat` with nbtlib — safe, because it's already a valid file.

The server jar is downloaded once (verified by SHA1) via Mojang's official
version manifest and cached under `~/.mc_world_gen/server/`.

## EULA

Running a Minecraft server requires accepting Mojang's EULA. This script writes
`eula=true` for you, which means **you accept** https://aka.ms/MinecraftEULA.

## Notes / trade-offs

- Each world takes roughly 10-30s (server boot + spawn gen + shutdown).
- Only the spawn area is pre-generated; the rest generates as you explore
  (normal Minecraft behaviour).
- Existing world folders in saves are skipped, not overwritten.
- Increase the per-world timeout in `run_server_generate` if you generate on a
  slow disk/CPU.

## Settings reference

```python
SETTINGS = {
    "gamemode": 0,                   # 0=Survival 1=Creative 2=Adventure 3=Spectator
    "difficulty": 2,                 # 0=Peaceful 1=Easy 2=Normal 3=Hard
    "hardcore": 0,                   # 0/1
    "pvp": 1,                        # 0/1
    "spawn_monsters": 1,             # 0/1
    "spawn_animals": 1,              # 0/1
    "spawn_npcs": 1,                 # 0/1
    "generate_structures": 1,        # 0/1
    "allow_commands": 0,             # cheats, 0/1
    "retain_inventory_on_death": 0,  # keepInventory, 0=drop 1=keep
}
```
