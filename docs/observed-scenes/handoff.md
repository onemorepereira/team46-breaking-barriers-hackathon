# Handoff: result tiles show the observed scene

Date: 2026-11-05.

## Problem
LGND returns, for each result chip, its index (`s2` or `naip`), the observation date and the footprint, but no image. The console filled the gap with a basemap mosaic: EOX's 2023 Sentinel-2 cloudless for `s2`, and USGS's latest NAIP for `naip`. So a result observed on 2026-02-10 was shown with a picture of the place from another date. That's the wrong evidence for a reviewer checking what the tool matched.

## What changed
- **`harness/scenes.py`** finds the scene observed that day that covers the chip, preferring one that covers the whole footprint, then the least cloudy. It reads only the chip's window from the scene's Cloud-Optimized GeoTIFF (`rasterio`, RGB bands, aspect kept, 384 px), then encodes a JPEG (`Pillow`).
  - **`s2`:** Sentinel-2 L2A `visual` (true colour, 10 m) via Element84 Earth Search, which reads the AWS open-data bucket `sentinel-cogs` with no key.
  - **`naip`:** NAIP `image` via Microsoft Planetary Computer, signed with its anonymous SAS token. The token is cached for 50 minutes; tokens last about an hour.
- **Tile flow:** a chip tile carries the observed date: `/tiles/chip/{idx}/{bbox}.jpg?run=…&observed=YYYY-MM-DD`. Its disk-cache and archive keys include the date (`imagery.chip_key`). Undated keys are unchanged, so older archived mosaics still resolve.
- **Fallback:** `tiles.Cache.chip` tries the dated scene first. If it can't be found or read, it serves the mosaic, cached under the mosaic's key, so the scene is tried again next time.
- **Credit:** each tile's `tile_source` names the scene it came from ("Sentinel-2 L2A scene observed 2026-02-10 (Copernicus Sentinel data, via Element84 Earth Search)"). The imagery panel shows it.
- **Run archiving** (`archive_run_tiles`) archives the dated scene.
- **New dependencies:** `rasterio`, `pillow` and `numpy`, added to `tests/allowed_deps.txt` with the reason. `uv.lock` has cp312 manylinux aarch64 wheels for all three, so the `linux/arm64` agent image installs them.

## Licences
These are the sources `analysis/licences.py` already records for LGND's imagery: NAIP is public domain with attribution, and Sentinel-2 is Copernicus free and open, from the AWS `sentinel-2-l2a-cogs` registry entry. EOX's mosaic, now only a fallback, is CC BY-NC-SA 4.0 (no commercial use).

## Proof
- **Sources checked live (2026-11-05):**
  - Earth Search and Planetary Computer each return the observed item for a Jodhpur `s2` chip (2026-02-10) and an Abilene `naip` chip (2020-10-07).
  - Windowed reads took 6.9 s and 7.3 s cold, and 0.02 s and 0.9 s warm.
- **Planetary Computer's rendering API was unusable:** its `item/bbox` crop and its tiles both answered 504 after 15 s on every try. That's why scenes are read directly from storage instead.
- **Through the console:**
  - three Jodhpur `s2` tiles (2026-03-20, 2026-04-11) and three Abilene `naip` tiles (2020-10-07, 2022-09-09) were served from their scenes with no fallback: 15 s for the first, about 2 s each after that;
  - the Jodhpur tile shows the solar park, and the 2022 NAIP tile shows an array under construction.
- **Tests:** `tests/test_scenes.py` covers dated URLs and keys, scene first, fallback with a later retry, catalogue choice and date validation. `tests/test_tiles.py` is updated for dated chips.

## Rollback
Revert the PR. Dated cache and archive files are simply no longer used, and undated mosaics resolve as before.
