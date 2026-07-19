# TextWorldExpress-CS3600

A fork of [cognitiveailab/TextWorldExpress](https://github.com/cognitiveailab/TextWorldExpress) that adds **full observability on demand**, for the CS3600 Intro-to-AI search assignment (BFS/DFS/A* in a partially-observable text environment).

For everything else -- what the games are (`coin`, `mapreader`, `cookingworld`, `twc`, etc.), their tunable parameters, gold paths, benchmarks, precrawled paths -- see the [original TextWorldExpress README](https://github.com/cognitiveailab/TextWorldExpress). This fork only adds the full-observability API described below; everything else works exactly like upstream.

**Before running:** you'll need Java installed.

## Install

Not published to PyPI -- install from a clone:

```bash
git clone https://github.com/markriedl/TextWorldExpress-CS3600.git
pip install -e ./TextWorldExpress-CS3600
```

## Launching the environment

```python
from textworld_express import TextWorldExpressEnv

env = TextWorldExpressEnv(envStepLimit=100)
env.load(gameName="coin", gameParams="numLocations=5,includeDoors=1,numDistractorItems=0")
obs, infos = env.reset(seed=3, gameFold="train", generateGoldPath=True)
```

This part is unchanged from upstream: `env.step(action)`, `infos['validActions']`, `env.getGoldActionSequence()`, etc. all work as usual.

## Full observability: `getInitialState()` / `getSuccessors()` / `getStateInfo()`

These let a search algorithm (e.g. your own BFS/DFS/A*) explore the environment's full state graph one state at a time, instead of only ever seeing the current room. They're backed by a search session on the Java side that's entirely separate from the interactive session above -- `getSuccessors()` never calls `step()` on `env`, so exploring hypothetical states during search can never be confused with actually playing the game.

```python
# Start a search session from wherever `env` currently is (usually right after reset()).
start_state = env.getInitialState(maxCacheSize=50000)
print(start_state["id"], start_state["location"], start_state["validActions"])

# Expand a state via one specific action -- getSuccessors(stateId, action) returns the single
# resulting state.
for action in start_state["validActions"]:
    state = env.getSuccessors(start_state["id"], action)
    print(action, "->", state["id"], state["location"])

# Re-fetch a state's info later if you only kept its id around (e.g. in a frontier list).
env.getStateInfo(start_state["id"])
```

Each state dict has the shape:
```python
{
  "id": "s0",
  "observation": "...", "look": "...", "inventory": "...",
  "location": "kitchen",           # ground-truth room name; "" for games without room structure
  "validActions": ["move north", ...],
  "scoreRaw": 0.0, "score": 0.0,

  # Ground truth for the *entire* world, not just what's visible from the current room:
  "rooms": {
    "kitchen": {
      "name": "kitchen",
      "x": 0, "y": 0,   # ground-truth grid position: north is +y, east is +x
      "contents": {
        "fridge": {"isOpen": False, "contents": {}, ...},
        "counter": {"isOpen": True, "contents": {"apple": {...}}, ...},   # items can be nested inside containers
        ...
      },
      "doorNorth": {"isOpen": False, ...}, "doorSouth": None, "doorEast": {...}, "doorWest": None,
      "locationNorth": None, "locationSouth": "backyard", "locationEast": None, "locationWest": "pantry",
      ...
    },
    "pantry": {...}, "backyard": {...}, ...   # every room, not just "kitchen"
  },
  "inventoryItems": ["coin"],   # ground-truth item names, as opposed to `inventory`'s display text
}
```
`rooms` (empty `{}` for games without room structure) is every room's contents/doors/adjacency/coordinates, reusing the engine's own recursive object serialization -- so it correctly reflects a door left open in a room you're not currently in, or a distractor item that happens to be nested inside a container rather than sitting directly in the room. `inventoryItems` (empty `[]` for games without this support) is a flat list of item names, alongside the natural-language `inventory` text you already get from `env.step()`.

Because every room's `x`/`y` and `locationNorth`/`locationSouth`/`locationEast`/`locationWest` are already present in a single state, things like "what's the layout of the map" or "which room is object X in" never require exploring the environment (calling `getSuccessors()`) to figure out -- they're a plain traversal over the `rooms` dict you already have from one `getInitialState()` call.

Note what's deliberately **not** here: the engine's own `taskSuccess`/`taskFailure` win/lose flags. Those are tied to whichever single built-in objective a game happens to define (e.g. the coin game's "is the coin in inventory"), so baking them into every search-API state would make it impossible to target a different objective (e.g. "pick up the coin *and* a specific distractor item") without new Scala-side game code. Define your own `is_goal()` from `rooms`/`inventoryItems`/`location` instead -- e.g. `"coin" in state["inventoryItems"]`. (The interactive `env.step()`/`env.reset()` session is unaffected -- `infos["score"]`/`taskSuccess`/`taskFailure` from ordinary play still work exactly as in upstream TextWorldExpress.)

In the coin game specifically, every pickupable object (the coin, and any `numDistractorItems` distractors) is always placed somewhere reachable without opening anything -- directly in a room, or on/in an always-open container like a counter or shelf -- since the agent has no action to open a closed container (fridge, cupboard, drawer, etc.) in this game. So `numDistractorItems=4` reliably gives you 4 extra pickupable objects (5 total, including the coin) to build multi-object objectives around.

Notes:
- `getSuccessors(stateId, action)` and `getStateInfo(stateId)` only accept ids that came from `getInitialState()` or a previous `getSuccessors()` call in the *current* search session -- calling `getInitialState()` again starts a fresh session and invalidates old ids. An unrecognized id, or an `action` that isn't one of that state's `validActions`, raises `RuntimeError`.
- Revisiting an already-seen state (a self-loop action, or reaching the same state via a different path) returns that state's existing `id` rather than minting a new one, so your visited-set/dedup logic works the way you'd expect.
- `maxCacheSize` bounds how large a single search session is allowed to grow -- expanding into a genuinely new state once the cache is full raises `RuntimeError`.
- Once your search returns a plan, execute it for real with ordinary `env.step()` calls -- searching never advances the live episode.

There's also a one-shot `env.getFullStateSpace()` (and a convenience wrapper env, `FullyObservableTextWorldExpressEnv`) that crawls and returns the *entire* reachable graph in one call, useful for small games or for rendering a map/state diagram; see the docstrings in `textworld_express/fully_observable.py` for details.
