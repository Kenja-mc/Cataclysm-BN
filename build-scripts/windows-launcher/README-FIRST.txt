Bright Nights Overhaul for Windows
==================================

Start the game
--------------
Double-click "Launch Bright Nights.bat".

The unsigned build may show "Windows protected your PC". Confirm the download came
from https://github.com/Kenja-mc/Cataclysm-BN/releases before choosing "More info"
and "Run anyway". Do not bypass warnings for an unknown download source.

You can also start cataclysm-bn-tiles.exe directly. Then the game does not
check for updates.

Updates
-------
Each time you use "Launch Bright Nights.bat", it asks GitHub if there is a newer
version. If there is one, it asks "Update to vX now? [Y/n]". Press Enter to update,
or type n to play the version you have. With no internet, the game just starts.

To check for an update at any time, double-click "Update Bright Nights.bat".

An update replaces the game files only. It keeps your saves, settings, and any mods,
tilesets, or soundpacks you added under their own folder names. Shipped folder names
belong to the release and are replaced. If an update fails, it restores the old files.
If recovery cannot finish, the launcher stops. Keep .bno-update\backup and the error
message, close any game/updater process, then try again. Never delete that backup
while recovery is incomplete. The updater does not support links or junctions.

Your files
----------
Everything stays in this folder:

  save\        your worlds and characters
  config\      your settings and key bindings
  memorial\    and graveyard\: records of dead characters
  templates\   saved character templates
  mods\        mods you add yourself (or data\mods\)
  gfx\         tilesets (you can add your own)
  sound\       soundpacks you add yourself (or data\sound\)

To move the game, move the whole folder. To back up your games, copy save\ and
config\. Do not put your own files in data\json\ or other data folders: an update
replaces them.

Version
-------
VERSION.txt shows the version you have. All releases:
https://github.com/Kenja-mc/Cataclysm-BN/releases
