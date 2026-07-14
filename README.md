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

# Expand a state into its successors.
for successor in env.getSuccessors(start_state["id"]):
    print(successor["action"], "->", successor["state"]["id"], successor["state"]["location"])

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
  "taskSuccess": False, "taskFailure": False,
}
```

Notes:
- `getSuccessors(stateId)` and `getStateInfo(stateId)` only accept ids that came from `getInitialState()` or a previous `getSuccessors()` call in the *current* search session -- calling `getInitialState()` again starts a fresh session and invalidates old ids. An unrecognized id raises `RuntimeError`.
- Revisiting an already-seen state (a self-loop action, or reaching the same state via a different path) returns that state's existing `id` rather than minting a new one, so your visited-set/dedup logic works the way you'd expect.
- `maxCacheSize` bounds how large a single search session is allowed to grow.
- Once your search returns a plan, execute it for real with ordinary `env.step()` calls -- searching never advances the live episode.

There's also a one-shot `env.getFullStateSpace()` (and a convenience wrapper env, `FullyObservableTextWorldExpressEnv`) that crawls and returns the *entire* reachable graph in one call, useful for small games or for rendering a map/state diagram; see the docstrings in `textworld_express/fully_observable.py` for details.
