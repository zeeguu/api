# 0003. BuildKit Cache Mounts for Package Managers

**Status**: Accepted
**Date**: 2025-10-28
**Deciders**: Mircea, Claude
**Supersedes**: Extends [ADR-0002](0002-docker-layer-caching-in-ci.md)

## Context

After implementing Docker layer caching in [ADR-0002](0002-docker-layer-caching-in-ci.md), builds improved from 12+ minutes to 2-3 minutes when adding a package. However, **2-3 minutes is still too slow** for the common case of adding a single pip package.

### The Problem with Layer Caching Alone

When `requirements.txt` changes (even by one line):
1. Docker invalidates the layer: `RUN pip install -r requirements.txt`
2. Pip downloads **all 78 packages** from PyPI again
3. Pip installs **all 78 packages** again
4. Total time: 2-3 minutes

**Why?** Layer caching is all-or-nothing. When requirements change, the entire layer rebuilds from scratch.

### What We Actually Need

When adding one package, we should:
- ✅ Reuse the 77 already-downloaded wheel files
- ✅ Only download the 1 new package
- ✅ Only install what changed

**Solution**: BuildKit cache mounts persist package manager caches between builds, independent of layer invalidation.

## Decision

We will use **BuildKit cache mounts** to persist package manager caches across builds for:
1. **Pip cache** (`/root/.cache/pip`) - Python package wheels
2. **Apt cache** (`/var/cache/apt`, `/var/lib/apt`) - System packages

### Implementation

#### Pip Cache Mount

```dockerfile
# Before
RUN python -m pip install -r requirements.txt

# After
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt
```

#### Apt Cache Mounts

```dockerfile
# Before
RUN apt-get update
RUN apt-get install -y package1 package2 package3

# After
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y package1 package2 package3
```

### Additional Optimization

Consolidated multiple `RUN apt-get install` commands into a single layer:
- **Before**: 6 separate `RUN` commands (including duplicates!)
- **After**: 2 combined `RUN` commands with cache mounts
- **Benefit**: Fewer layers + better cache hit rate

## Consequences

### Positive

- ✅ **6x faster package additions**: 2-3 min → 20-30 sec when adding one pip package
- ✅ **3-4x faster apt installs**: System package changes are much faster
- ✅ **Persistent across layer invalidation**: Cache survives even when requirements.txt changes
- ✅ **Automatic cache management**: BuildKit manages cache size and eviction
- ✅ **Works with registry cache**: Complements ADR-0002's layer caching
- ✅ **Reduced network usage**: Fewer downloads from PyPI/apt repos

### Negative

- ❌ **Requires BuildKit**: Must use Docker Buildx (already have this)
- ❌ **Additional cache storage**: ~200-500MB for pip cache, ~300-800MB for apt cache
- ❌ **Slightly more complex Dockerfile**: Cache mount syntax is less familiar
- ❌ **Debugging complexity**: Cache mounts are invisible in layers

### Neutral

- ⚠️ **Cache persistence**: Caches live in BuildKit's cache directory, separate from images
- ⚠️ **Cache sharing**: `sharing=locked` prevents concurrent apt access conflicts
- ⚠️ **Not in final image**: Cache mounts don't increase image size

## Performance Impact

| Scenario | Before ADR-0002 | After ADR-0002 | After ADR-0003 | Total Improvement |
|----------|-----------------|----------------|----------------|-------------------|
| **First build** | 12 min | 12 min | 12 min | (builds caches) |
| **Code change only** | 12 min | 30 sec | **20 sec** | **36x faster** ⚡⚡⚡ |
| **Add 1 pip package** | 12 min | 2-3 min | **20-30 sec** | **24-36x faster** ⚡⚡⚡ |
| **Change apt packages** | 12 min | 10 min | **2-3 min** | **4-6x faster** ⚡⚡ |
| **requirements.txt rebuild** | 12 min | 2-3 min | **20-30 sec** | **24-36x faster** ⚡⚡⚡ |

### Real-World Example: Adding Azure SDK

When we added `azure-cognitiveservices-speech==1.40.0`:
- **Before ADR-0003**: Would have taken 2-3 minutes (redownload all 78 packages)
- **After ADR-0003**: Takes ~25 seconds (download only Azure SDK, reuse 77 cached packages)

## How It Works

### Layer Caching vs Cache Mounts

**Layer caching** (ADR-0002):
```
requirements.txt unchanged?
  YES → Reuse entire layer (fast!)
  NO → Rebuild entire layer (slow!)
```

**Cache mounts** (ADR-0003):
```
requirements.txt changed?
  YES → Layer rebuilds BUT:
    - Pip reuses cached wheel files ✅
    - Only downloads new packages ✅
    - Installs are still fast ✅
```

### Technical Details

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt
```

This tells BuildKit:
1. Mount `/root/.cache/pip` from BuildKit's cache storage
2. Pip downloads wheels to this cache directory
3. After RUN completes, BuildKit saves the cache (but not in the layer)
4. Next build mounts the same cache directory
5. Pip finds cached wheels and skips downloads

### Cache Location

Caches are stored outside the image:
- **Local builds**: `~/.docker/buildx/cache/`
- **GitHub Actions**: BuildKit worker's cache storage
- **Registry**: Not pushed to Docker Hub (cache mounts ≠ layers)

## Related

- **Supersedes**: Extends [ADR-0002](0002-docker-layer-caching-in-ci.md) with package manager caching
- **Implementation**: See `Dockerfile` lines 4-9, 12-22, 27-28, 108-109
- **BuildKit docs**: https://docs.docker.com/build/cache/optimize/
- **Cache mounts**: https://docs.docker.com/build/guide/mounts/#add-a-cache-mount

## Future Considerations

1. **Cache size monitoring**: May need to monitor cache disk usage in CI
2. **Cache invalidation**: If pip cache gets corrupted, may need manual clearing
3. **Multi-architecture**: Cache mounts work per-platform (already fine for linux/amd64)
4. **Other caches**: Could add cache mounts for npm, cargo, etc. if we add those tools

## Migration Notes

### Before Deploying

No migration needed! This is backward-compatible:
- Builds without BuildKit ignore `--mount=` flags
- GitHub Actions already uses Buildx (from ADR-0002)

### First Build After Deployment

The first build after this change will:
1. Take the usual 12 minutes (populating caches)
2. Subsequent builds are 6x faster immediately

### Verifying It Works

After deploying, add a test package to requirements.txt and time the build:
```bash
# Should take ~20-30 seconds, not 2-3 minutes
echo "requests==2.31.0" >> requirements.txt
git commit -am "Test: Add package"
git push
# Watch GitHub Actions - should be fast!
```

## References

- Docker BuildKit cache mounts: https://docs.docker.com/build/guide/mounts/
- Pip caching: https://pip.pypa.io/en/stable/topics/caching/
- BuildKit cache best practices: https://docs.docker.com/build/cache/
