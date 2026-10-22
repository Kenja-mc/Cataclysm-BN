# Tileset license sweep: bundled sets and outside candidates

Scope: every tileset under `gfx/`, the BN external tileset sheets, `LICENSE.txt`, and
outside art that could be imported into a CC BY-SA 3.0 game. This extends
`docs/fork/asset-credits.md`; it does not replace the per-sprite notices in the upstream
tileset repositories.

Evidence: upstream `tileset.txt` files, CDDA and CDDA-Tilesets commits, author pages,
Creative Commons primary pages, and local `tile_config.json` sprite indices. Local image
claims cite the sheet and `fg` index. Crops used for the two jerky checks are in
`/tmp/texture-sweep/`.

Two conventions:

- "Recorded" means a license notice in the upstream project or an author page. A local
  `tileset.txt` that only names the tileset is not a license grant.
- Perspective is `[INFERENCE]` from the pack category and tile grid where the license or
  asset page does not state it. Style-fit notes are `[INFERENCE]` throughout.

## Bundled tilesets

| Tileset (path) | Grid and style | Credited authors | Recorded license and source | Redistribution verdict for a CC BY-SA 3.0 game |
| --- | --- | --- | --- | --- |
| ASCII, `gfx/ASCIITileset/` | 10x10 ASCII glyph sheet, 80 sprites (`tile_info.json`). Descends from the RetroDays ASCII fallback; halfahermit cleaned and relinted it in 2019. | **halfahermit** for the 2019 sheet; **Antistar (Joseph Lollback)** for the RetroDays ASCII lineage; **HRose** and **Trihook** behind that lineage. | No local license notice. Upstream CDDA project was CC BY-SA 3.0 at commit [57f0ab6097](https://github.com/CleverRaven/Cataclysm-DDA/commit/57f0ab609778e782fe442ecf569f50438f8fc96b). RetroDays is declared CC BY-SA 4.0 by its author. | Qualified. The sheet is a RetroDays derivative, so the 4.0 notice applies. The Trihook charset status below is unresolved. |
| BrownLikeBears, `gfx/BrownLikeBears/` | 20x20, pastel palette, 16 sprite columns (`tile_info.json`). Based on RetroDays. | **StopSignal**. | No local notice. Upstream CDDA-Tilesets states: "BrownLikeBears is a neat 20X20 tileset based on Retrodays and created by StopSignal", [tileset.txt](https://github.com/I-am-Erk/CDDA-Tilesets/blob/master/gfx/BrownLikeBears/tileset.txt). Repository-wide license is CC BY-SA 3.0, [README](https://github.com/I-am-Erk/CDDA-Tilesets#licensing). | Qualified. As a RetroDays derivative it inherits the 4.0 share-alike, despite the upstream 3.0 label. |
| ChestHole16, `gfx/ChestHole16Tileset/` | 16x16, 16 sprite columns (`tile_info.json`). | **Sean "Chezzo" Osman**, **Lukas Courtial "Zava"**, **VoidDweller**; chain credits Daftigod, Pixelhack, Mindflayer, John Shaw (Absurd), mshock, egomassive, Arex, Coleen, Waldo, Tsu, Sir Hoder, Blockhead, Ragamer, Deon, ChunkofMeat, Oakforce, Ruxe. | No standalone license. Chezzo added it directly to CDDA under the project CC BY-SA 3.0: [commit 48f99ac5fb](https://github.com/CleverRaven/Cataclysm-DDA/commit/48f99ac5fb955e8e1aed35541993a7ee5a49d1bc), [LICENSE at that commit](https://github.com/CleverRaven/Cataclysm-DDA/blob/48f99ac5fb955e8e1aed35541993a7ee5a49d1bc/LICENSE.txt). | Qualified. License is 3.0, but provenance is compromised: the `jerky` tile at `tiles.png` fg 881 is named in the HarvestCraft removal, and the Blockhead/Raga chain is flagged in [PR 34196](https://github.com/CleverRaven/Cataclysm-DDA/pull/34196). |
| HitButton iso, `gfx/HitButton_iso/` | 16x20 isometric cells, pixel-doubled (`tile_info.json`: `width 16`, `height 20`, `iso: true`, `pixelscale: 2`). | **HitButton** (original), **I-am-Erk** (remake as SmashButton iso). | Upstream tileset.txt: "imported from Cataclysm:Dark Days Ahead under Creative Commons Attribution-ShareAlike 3.0 Unported License", [tileset.txt](https://github.com/I-am-Erk/CDDA-Tilesets/blob/master/gfx/HitButton_iso/tileset.txt). Original commit by hitbutton: [277ae7b616](https://github.com/CleverRaven/Cataclysm-DDA/commit/277ae7b61651dce0bc5258b9a98ce5bb48ab7a74). | Yes, CC BY-SA 3.0. Keep the HitButton and I-am-Erk credits. |
| Hoder's, `gfx/HoderTileset/` | 16x16, 16 sprite columns (`tile_info.json`). | **SirHoder**. | No standalone notice. SirHoder committed the tileset directly to CDDA in 2013 and 2014 under the project CC BY-SA 3.0: [f0405aeef1](https://github.com/CleverRaven/Cataclysm-DDA/commit/f0405aeef1ae00e21d3f7ae509207d6083bfb915), [bd43266064](https://github.com/CleverRaven/Cataclysm-DDA/commit/bd4326606437cea083fd3fd9666e6290045ed941), [LICENSE.txt at f0405aeef1](https://github.com/CleverRaven/Cataclysm-DDA/blob/f0405aeef1ae00e21d3f7ae509207d6083bfb915/LICENSE.txt). | Yes, CC BY-SA 3.0, on repository-contribution evidence. No separate author license text was found. |
| MSX++ UnDeadPeople Edition, `gfx/MSX++UnDeadPeopleEdition/` | 32x32 default; 64x80 and 160x128 sheets also present (`tile_config.json` `tile_info`). Fork default tileset. | **SomeDeadGuy** (maintainer); base by **Xotto**, **Waldo**, **Tsu**, **SirHoder**, **Coleen**, **Mshock**. Forum credit list: [post 21](https://discourse.cataclysmdda.org/t/32x32-msx-dead-people-tileset/18775/21). | Base MShockXotto+ imported under CC BY-SA 3.0, [tileset.txt](https://github.com/I-am-Erk/CDDA-Tilesets/blob/master/gfx/MShockXotto%2B/tileset.txt). UDP was re-added to CDDA in 2020 by [commit 4c62715d7b](https://github.com/CleverRaven/Cataclysm-DDA/commit/4c62715d7b531388871aced60c7eeaee40f0af1f) (project CC BY-SA 3.0; the commit message records no provenance review). Local `fork_fill_CREDITS.md` records CC BY-SA 3.0 for borrowed sprites. | Qualified, three caveats: (1) the `jerky` tile at `normal_items.png` fg 2823 is named in PR 34196; (2) the UDP README says it uses **Nearly Dead** assets by Xotto and Toro by permission, not under a named license; (3) no license file was found in the maintained repo or the mirrors checked, only README attribution. |
| RetroDays, `gfx/RetroDaysTileset/` | 10x10, pixel-doubled (`tile_info.json`), 16 sprite columns. | **Antistar (Joseph Lollback)**, based on **HRose**'s unfinished Retro/ASCII tileset, using some tiles from **Trihook**'s "c= roguelike charset". | Author page: "RetroDays is released under a CC-BY-SA license (http://creativecommons.org/licenses/by-sa/4.0/)", [Nexus mods/1](https://www.nexusmods.com/cataclysmdarkdaysahead/mods/1?tab=description). The same 4.0 text is in the [May 2014 Wayback snapshot](http://web.archive.org/web/20140508002706/http://www.nexusmods.com/cataclysmdarkdaysahead/mods/1), before the CDDA import. CDDA-Tilesets instead records a 3.0 import, [tileset.txt](https://github.com/I-am-Erk/CDDA-Tilesets/blob/master/gfx/Retrodays/tileset.txt). | Qualified, but not 3.0. Treat the tileset as CC BY-SA 4.0. Modified sprites must stay 4.0 under the [CC compatible-license rules](https://creativecommons.org/compatible-licenses/). |
| RetroDays+, `gfx/RetroDays+Tileset/` | 10x10, pixel-doubled (`tile_info.json`). RetroDays with transparency. | **captnblood** (merged as GitHub user `app`). | No local notice. Merged into CDDA under the project CC BY-SA 3.0: [PR 36424](https://github.com/CleverRaven/Cataclysm-DDA/pull/36424), [commit e4e33a0833](https://github.com/CleverRaven/Cataclysm-DDA/commit/e4e33a0833e696413e0129f317a5603f5ffa28fe). It is a RetroDays derivative. | Qualified. Derivative of RetroDays 4.0, so the 4.0 share-alike applies. The CDDA 3.0 merge label does not override the source license. |
| UltimateCataclysm (UltiCa), `gfx/UltimateCataclysm/` | 32x32 main grid, 20x20 small sprites (`tile_config.json`). | **I-am-Erk** and CDDA-Tilesets contributors; filler trees by **Yar**, edited by I-am-Erk. | Repository-wide CC BY-SA 3.0, [README](https://github.com/I-am-Erk/CDDA-Tilesets#licensing) and [LICENSE.txt](https://github.com/I-am-Erk/CDDA-Tilesets/blob/master/LICENSE.txt). Per-tile credits in upstream folders. | Yes, CC BY-SA 3.0. Per-tile attribution remains in the upstream repository. |
| BN external tileset sheets, `data/json/external_tileset/` | 32x32 sheets, plus mutation and tall sheets. | BN and DDA contributors; PR list in [README](../../../../data/json/external_tileset/README.md). | No license section. Contributions land in a CC BY-SA 3.0 repository; ports from DDA are CC BY-SA 3.0. | Project default 3.0. No per-sprite map. The UDP-derived sheets inherit the MSX++ caveats. |
| Root fallback `gfx/tinytile.png` | 16x16 fallback sheet. | Cataclysm contributors; no separate artist notice. | Project default, `LICENSE.txt`. | Project default only; no independent provenance. |

### Bundled findings that change the credits index

1. **RetroDays is 4.0, not 3.0.** The author's page and the May 2014 archive both name
   CC BY-SA 4.0. The CDDA-Tilesets 3.0 label is a downstream import claim. Consequence:
   RetroDays, RetroDays+, BrownLikeBears, and the ASCII sheet form a 4.0 share-alike chain.
   The fork should ship a per-tileset 4.0 notice for those sets, or obtain a written 3.0
   grant from Antistar. This is a concrete compliance gap, not a style note.
2. **Trihook's charset changed status twice.** The CSDb thread first says "If anyone needs
   the tiles feel free to use them" (2013-03-21), then "As of today, (7.9.2014) this
   tileset is not free anymore, I'm changing the licence to something sellable"
   (2014-09-07), then "the licence for c64 has changed its status to free" (2016-04-06).
   Source: [CSDb roguelike charset thread](https://csdb.dk/forums/?roomid=13&topicid=97045&showallposts=1).
   No named license was ever posted. RetroDays, RetroDays+, BrownLikeBears, and the ASCII
   sheet inherit this uncertainty. [UNVERIFIED] whether Antistar's "kind permissions of
   everyone involved" covers redistribution after the 2014 revocation.
3. **HarvestCraft jerky tile.** CDDA removed the MShock-family sets over a `jerky` sprite
   traced through BlockHead and Raga to the Minecraft HarvestCraft mod: [PR 34196](https://github.com/CleverRaven/Cataclysm-DDA/pull/34196).
   Local entries: MSX++ `jerky` at `normal_items.png` fg 2823, and ChestHole16 `jerky` at
   `tiles.png` fg 881. Crops: `/tmp/texture-sweep/msx_jerky.png` and
   `/tmp/texture-sweep/chesthole_jerky.png`. PR 34196 also says the whole Raga-sourced
   portion is suspect, not only this sprite.
4. **MSX++ uses Nearly Dead art by permission only.** The UDP README says: "This tileset
   uses resources from the upcoming game 'Nearly Dead' by Xotto and Toro, which was
   generously provided by Xotto", [README mirror](https://github.com/jmz-b/UndeadPeopleTileset).
   A permission is not a named license and no scope or redistribution clause is recorded.
   [UNVERIFIED] whether redistribution in a CC BY-SA release is covered.
5. **Authors now nameable.** Hoder's is **SirHoder**; RetroDays is **Antistar (Joseph
   Lollback)**, **HRose**, **Trihook**; RetroDays+ is **captnblood**; HitButton iso is
   **HitButton** and **I-am-Erk**; BrownLikeBears is **StopSignal**; ASCII is
   **halfahermit** on the RetroDays ASCII lineage. These close the "artists not individually
   listed" rows for those five sets.
6. **No local tileset.txt is a license grant.** All nine local files are name/path metadata
   only. Existing credits rely on upstream repository licenses and commit history. The
   fork's `LICENSE.txt` default is a fallback, not proof of import permission.
7. **ChestHole16's per-tile split is still missing.** The tileset.txt gives a chain of
   names but not which of Zava, VoidDweller, or the older artists drew which sprite.

## Outside candidates

"Compatible" means the art can be included in a CC BY-SA 3.0 game with the stated
conditions. It does not mean the whole game must change license.

| Source | License, verbatim and link | Compatible with CC BY-SA 3.0? | Grid and perspective | Coverage | Style fit | Attribution |
| --- | --- | --- | --- | --- | --- | --- |
| **Dungeon Crawl Stone Soup tiles**, [crawl/tiles](https://github.com/crawl/tiles) | **CC0 1.0**, "CC Zero", [README](https://github.com/crawl/tiles/blob/master/README.md), [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/) | Yes, no conditions. Exclude tiles listed in [TILES_UNDER_UNKNOWN_LICENSE.md](https://github.com/crawl/tiles/blob/master/TILES_UNDER_UNKNOWN_LICENSE.md); those are not CC0. | 32x32 top-down; verified with `releases/Nov-2015/mon/aberr/unseen_horror.png` (32x32). | Monsters, items, dungeon terrain, GUI, effects, player; directory listing confirms all six groups. | High. Same 32px cell as MSX++ and UltiCa; colorful detailed pixel art. Already used by Magical Nights. | Not required. Courtesy credit to DCSS artists is good practice. |
| **Kenney 1-Bit Pack**, [kenney.nl](https://kenney.nl/assets/1-bit-pack) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/); Kenney FAQ confirms "Attribution is not required", [support](https://kenney.nl/support). | Yes, no conditions. | 16x16 top-down, 1-bit; 1078 files. | Roguelike/RPG terrain, items, creatures, UI symbols. | High for clarity. Monochrome silhouettes read at small sizes; good for ASCII-adjacent or RetroDays-style views, not a drop-in for MSX++. | None required. |
| **game-icons.net**, [game-icons.net](https://game-icons.net/about.html) | **CC BY 3.0** ("Creative Commons 3.0 BY"), [license text](https://creativecommons.org/licenses/by/3.0/). | Yes with attribution. Modified icons can be distributed under BY-SA 3.0 with credit. | SVG and PNG icons, no fixed tile grid. Design for 24/32/64px UI cells; downscale as needed. | 4000+ status, effect, need, body, bionic and action icons. | High for UI, not map tiles. Fills the HUD/status-art gap; vector originals keep edges clean at 16 to 32px. | Credit each icon author, for example "Icons made by Delapouite, Lorc. Available on https://game-icons.net". |
| **LPC Tile Atlas**, [OpenGameArt](https://opengameart.org/content/lpc-tile-atlas) | **CC-BY-SA 3.0** and **GPL 3.0** dual, [CC BY-SA 3.0 text](https://creativecommons.org/licenses/by-sa/3.0/), [LPC about](https://lpc.opengameart.org/). | Yes via the CC BY-SA arm. Do not rely on the GPL arm. Derivative tiles stay CC BY-SA 3.0. | 32x32 top-down, front-facing overhead. | Terrain, farming, plants, outdoor and dungeon ground. | Medium. Fantasy palette and outlines; usable for terrain and furniture after recoloring, weaker for modern apocalypse props. | Credit the artists in the atlas `Attribution.txt` and keep the share-alike notice. |
| **DawnLike 16x16**, [OpenGameArt](https://opengameart.org/content/dawnlike-16x16-universal-rogue-like-tileset-v181) | **CC-BY 4.0**, [license text](https://creativecommons.org/licenses/by/4.0/). | Yes with attribution. Modified sprites should carry BY-SA 4.0, so use a mixed-license notice. | 16x16 top-down. | Universal roguelike set: monsters, items, terrain, UI, characters. | Medium. NetHack/DawnBringer look; good for a 16px or scaled-up clarity pass, less fitting for 32px MSX++. | Credit DragonDePlatino. |
| **RLTiles**, [rltiles.sourceforge.net](https://rltiles.sourceforge.net/) | **Public domain**, with a requested notice: "Part of (or All) the graphic tiles used in this program is the public domain roguelike tileset 'RLTiles'..." [site notice](https://rltiles.sourceforge.net/). RogueBasin describes it as "public domain with a request for attribution", [RogueBasin](https://www.roguebasin.com/index.php/Finding_graphical_tiles). | Yes. Public domain is compatible; include the requested notice. | 32x32 orthographic, some 64x64 isometric. | NetHack and Dungeon Crawl monsters, items, dungeon features, player parts. | Medium. Old-school 32px art; usable for monsters and items, less consistent with MSX++ shading. | Include the RLTiles notice text and the contributor list. |
| **16x16 DungeonTileset II** by 0x72, [itch.io](https://0x72.itch.io/dungeontileset-ii) | **CC0** ("CC-0"), author page. | Yes, no conditions. | 16x16 top-down. | Dungeon walls, floors, doors, heroes, monsters, items, animated props. | Medium. Clean cartoon dungeon style; limited modern or urban content. | Not required. |
| **Tiny 16: Basic** by Sharm, [OpenGameArt](https://opengameart.org/content/tiny-16-basic) | **CC-BY 4.0**, **CC-BY 3.0**, **OGA-BY 3.0**, page license field. | Yes with attribution; choose the CC BY 3.0 arm for the simplest 3.0 notice. | 16x16 top-down. | General RPG and roguelike terrain, characters, items, monsters. | Medium. Generic fantasy; needs recoloring for Cataclysm's palette. | Credit Sharm and keep the license notice. |
| **Kenney Roguelike/RPG pack**, [kenney.nl](https://kenney.nl/assets/roguelike-rpg-pack) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | 16x16 top-down; 1700 files. | Town, furniture, items, buttons, panels, terrain. | Medium. Clean cartoon look; strong for furniture and item icons, weak for gore and decay. | None required. |
| **Kenney Micro Roguelike**, [kenney.nl](https://kenney.nl/assets/micro-roguelike) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | 8x8 top-down, 1-bit; 320 files. | Minimal roguelike creatures, items, terrain. | Medium for overmap, minimap or dense UI; too small for the main 32px map. | None required. |
| **Kenney Tiny Dungeon**, [kenney.nl](https://kenney.nl/assets/tiny-dungeon) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | 16x16 top-down; 130 files. | Dungeon and sewer tiles, characters, props. | Medium. Small, clean set; useful for lab and sewer filler. | None required. |
| **Kenney Game Icons**, [kenney.nl](https://kenney.nl/assets/game-icons) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | UI icon sheet, 105 icons; native size not stated on the page [UNVERIFIED]. | Gamepad, prompt, interface icons. | Medium. UI only; less thematic than game-icons.net for survival status effects. | None required. |
| **Kenney UI Pack**, [kenney.nl](https://kenney.nl/assets/ui-pack) | **Creative Commons CC0**, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | UI panels, buttons, sliders; 430 files. | HUD frames, buttons, sliders. | Medium. Clean vector-like UI; would need a dark recolour to match Cataclysm. | None required. |
| **Cataclysm DDA Overmap Tiles** by BMacZero, [OpenGameArt](https://opengameart.org/content/cataclysmdda-overmap-tiles) | **CC0**, page license field, [CC0 text](https://creativecommons.org/publicdomain/zero/1.0/). | Yes, no conditions. | Overmap tiles, not the local map grid. | Field, forest, road overmap symbols. | High for overmap readability, not a source for map sprites. | None required. |

### Not usable or high risk

| Source | Reason |
| --- | --- |
| **Oryx Design Lab** tilesets, [license](https://www.oryxdesignlab.com/license) | The license says the files "MAY NOT BE REDISTRIBUTED" and are for the licensee's use. Paid royalty-free is not open-license redistribution. Not usable in an open-source release. |
| **GPL-only art** | The game ships as CC BY-SA 3.0, not GPL. Dual-licensed LPC art is fine via the CC arm; art offered only under GPL is not a clean fit. |
| **NC or ND packs** | NonCommercial conflicts with the project's unrestricted redistribution; NoDerivatives blocks the sprite edits needed for tilesheets. |
| **Unclear "free" permissions** | A forum post, "not copyrighted", or a bare "feel free to use" is not a license with defined terms. Treat as unresolved, as with Trihook's charset. |

## Recommendation: the three most useful sources

1. **DCSS tiles ([crawl/tiles](https://github.com/crawl/tiles)).** Use for missing monsters,
   items, terrain, effects and GUI sprites at 32x32. It matches the default MSX++/UltiCa cell
   size, is CC0, needs no attribution, and has a published exclusion list so the non-CC0
   tiles can be avoided. This is the lowest-risk way to fill broad content gaps.
2. **Kenney 1-Bit Pack ([kenney.nl](https://kenney.nl/assets/1-bit-pack)).** Use for clarity
   work: 16x16 monochrome silhouettes for status, UI, overmap and any tile where the current
   32px art is visually noisy. CC0, no attribution, and the 1-bit constraint forces readable
   shapes. It pairs naturally with the ASCII and RetroDays views.
3. **game-icons.net ([game-icons.net](https://game-icons.net/about.html)).** Use for status,
   need, mutation, bionic and weather icons that have no dedicated sprite today. CC BY 3.0
   with per-author credit, scalable SVG originals, and a much larger icon vocabulary than
   the bundled sheets. It fixes UI gaps that a terrain tileset cannot.

Runner-up: **LPC Tile Atlas** if the gap is outdoor terrain and farming rather than UI.
It is 32x32 and CC BY-SA 3.0, but the fantasy palette needs recoloring.

## Gaps closed

- Hoder's tileset author: **SirHoder**, with CDDA contribution commits under CC BY-SA 3.0.
- RetroDays author and lineage: **Antistar (Joseph Lollback)**, **HRose**, **Trihook**;
  license is **CC BY-SA 4.0**, not 3.0.
- RetroDays+ author: **captnblood**; CDDA merge PR 36424; RetroDays derivative.
- HitButton iso authors: **HitButton**, remake by **I-am-Erk**; CC BY-SA 3.0.
- BrownLikeBears author: **StopSignal**; RetroDays derivative.
- ASCII sheet: **halfahermit** 2019 cleanup of the RetroDays ASCII lineage.
- MSX++ lineage: **SomeDeadGuy**, **Xotto**, **Waldo**, **Tsu**, **SirHoder**, **Coleen**,
  **Mshock**, plus **Nearly Dead** by Xotto and Toro.
- UltiCa filler trees: **Yar**, edited by I-am-Erk (already recorded, now tied to the upstream
  repository license).

## Gaps not closed

- **Exact per-sprite provenance** for MSX++, ChestHole16 and the BN external sheets. The
  HarvestCraft/BlockHead/Raga chain is known at the tile-name level, not mapped across every
  sprite.
- **Nearly Dead permission scope.** No license text, no list of which sprites, no
  redistribution clause.
- **Trihook charset status.** The author changed the terms twice and never named a license.
  This affects RetroDays, RetroDays+, BrownLikeBears and ASCII.
- **RetroDays 3.0 versus 4.0.** The author says 4.0; CDDA-Tilesets records 3.0. No written
  3.0 grant was found.
- **Hoder standalone license.** Only repository-contribution evidence exists.
- **ChestHole16 artist-to-sprite split.** The chain of names is recorded, but not which
  artist drew which tile.
- **UDP repository license file.** None found in the maintained repo or the mirrors checked.
- **DCSS coverage is not blanket CC0.** The exclusion list must be filtered before import.
