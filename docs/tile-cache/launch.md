# Tile Cache and Archived Result Tiles: Launch

**Ship:** merged to `main` with the rest of the harness (originally via `design/eval-harness`, merged 2026-11-04). Nothing is deployed. The tile cache runs in the operator's console (`harness ui`), and archiving runs in the harness on the operator's machine. The AgentCore runtime is unchanged.

**Rollout:** on by default through `harness.yaml`:

```yaml
tiles: {archive: true, serve: true, cache_max_mb: 1024, max_age_days: 30}
```

**Backfill** (optional): tiles for older runs are archived on their next replay or judge. To do every run now:

```bash
for id in $(python3 -c "import json;print(' '.join(json.load(open('out/index.json'))['runs']))"); do uv run harness replay "$id"; done
```

Runs in S3 need the sandbox credentials sourced first.

**Monitor:**
- **Response headers:** `X-Tile-Origin` on every tile response (`cache`, `archive`, `upstream`, `stale`). Many `stale` responses mean a provider is struggling.
- **CLI output:** `run <id>: tiles {...}` on stderr whenever a replay or judge leaves tiles `failed` or `skipped`. Re-running `harness replay <id>` completes them.
- **Disk:** `du -sh out/tile-cache`, which should stay near `cache_max_mb`.

**Runbook:**

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Blank basemap tiles | Provider down, tile never cached | Switch basemaps (the map's buttons), or wait. A 502 is expected |
| Blank result tiles on an archived run | Run never archived | `harness replay <id>` while online |
| Tiles slow for about a minute after an S3 error | The archive breaker is open (60 s), so tiles come from the provider | None; it closes on its own |
| Cache too big | Cap set too high | Lower `tiles.cache_max_mb` and restart the console (it evicts at startup), or delete `out/tile-cache/` |

**Rollback:**
- `tiles.serve: false` then a console restart: the browser loads every tile from the providers again.
- `tiles.archive: false`: no more archiving.
- A full revert of the commits restores the old behavior. Archived tiles stay as unused files, and `out/tile-cache/` can be deleted.
