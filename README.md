# TextWorldExpress (CS3600 full-observability fork)
TextWorldExpress is a highly optimized reimplementation of three text game benchmarks focusing on instruction following, commonsense reasoning, and object identification.  TextWorldExpress is intended for natural language processing research, and a system description can be found in the Arxiv preprint [TextWorldExpress: Simulating Text Games at One Million Steps Per Second (PDF)](https://arxiv.org/abs/2208.01174).

This fork ([cognitiveailab/TextWorldExpress](https://github.com/cognitiveailab/TextWorldExpress)) adds two ways to get full observability over an otherwise partially-observable environment, on demand, over the existing py4j link: `getFullStateSpace()`, which crawls and returns the entire reachable state graph for whatever game/seed is currently loaded in one call (see [Full State Space (On Demand)](#full-state-space-on-demand)), and `getInitialState()`/`getSuccessors()`, which let a search algorithm (e.g. a student's own BFS/DFS/A*) drive the exploration one state at a time instead (see [Incremental State Space](#incremental-state-space-for-driving-your-own-search)). It exists to support the CS3600 Intro-to-AI homework on search in partially-observable text environments, replacing an earlier workflow of pre-crawling and shipping around per-seed JSON files.

#### Watch the system demonstration video on Youtube
[![Watch the video](https://user-images.githubusercontent.com/660004/182846595-f5379a83-0749-4bbc-91c9-a406ed1a2043.png)](https://youtu.be/MG6Ac4Xo6Ds)


# Quickstart
**Before running:** You will need `Java 1.8` installed on your system (shipped with most linux distributions).

This fork isn't published to PyPI -- install it from a local clone instead:

    conda create --name textworld-express python=3.8
    conda activate textworld-express
    git clone <this-repo-url>
    pip install -e ./TextWorldExpress-CS3600   # or whatever you named the clone

(The upstream, unforked package is also available via `pip install textworld-express` if you don't need `getFullStateSpace()`/`FullyObservableTextWorldExpressEnv`.)

Run an example random agent, on the Coin Collector game...:

    python examples/random_agent.py --game-name=coin

Run a user console where you can interact with the environment, on CookingWorld...:

    python examples/human.py --game-name=cookingworld


# Web Server Demo

A web server demo is also available, that allows running a TextWorldExpress user console that can be interacted with in a web browser.

To run the web server demo:

    conda create --name textworld-express python=3.8
    conda activate textworld-express
    pip install textworld-express[webserver]


Run the web server:

    python examples/textworldexpress-web-server.py

Point your web browser to [localhost:8080](https://localhost:8080).


# TextWorldExpress Design
TextWorldExpress is written in Scala (2.12.9), and compiles using `sbt` into a JAR file that is run with `java`. For convenience, a `python` API is provided, which interfaces using the `py4j` package.

## Environments

TextWorldExpress includes high-speed versions of three popular benchmark environments for text-game research. Additionally, it also includes 4 exclusive environments to study arithmetic, navigation, and neurosymbolic reasoning.

### CookingWorld ("cookingworld")
The CookingWorld environment tasks agents with preparing meals by following the instructions in a recipe that is provided in the environment. Agents must first collect required food ingredients (e.g., milk, bell pepper, flour, salt) that can be found in the environment in canonical locations (e.g., kitchen, pantry, supermarket, garden) and containers (e.g., fridge, cupboard). Randomly generated recipes require agents to first use a knife to prepare food by *slicing*, *dicing*, or *chopping* a subset of ingredients, then additionally using an appropriate heating appliance to *fry*, *roast*, or *grill* the ingredients. If all ingredients are prepared according to the recipe, the agent can use an action to *prepare the meal*, and finally *eat the meal* to complete the task successfully. Task complexity can be controlled by varying the number of locations in the environment, the number of ingredients required for the recipe, and the number of distractor ingredients randomly placed in the environment that are not required for the recipe. The recipes and environments are parametrically generated, with subsets of ingredients and specific preparations held out between training, development, and test sets to prevent overfitting. CookingWorld was originally created for the [First TextWorld Problems competition](https://aka.ms/ftwp) and later named by [[Madotto etal., 2020]](https://www.ijcai.org/proceedings/2020/207).

### TextWorld Commonsense ("twc")
Text game agents frequently learn the dynamics of environment -- such as the need to open a door before one can move through it -- from interacting with the environment itself, rather than using a pre-existing knowledge base of common sense facts or object affordances that would speed task learning. [TextWorld Commonsense](https://github.com/IBM/commonsense-rl) [[Murugesan etal., 2021]](https://arxiv.org/abs/2010.03790) aims to evaluate agents on common sense knowledge that can not be directly learned from the environment by providing agents a clean-up task where the agent must place common household objects (e.g., *a dirty dish*) in their canonical locations (e.g., *the dishwasher*) that can be found in knowledge bases such as ConceptNet. Separate lists of objects are used in the training, development, and test sets, meaning the agent can not learn object locations from the training set alone, and must rely on an external common sense knowledge base to perform well on the development and test sets. TextWorld Commonsense benchmark has three task difficulty levels, with the easiest including a single location and object to put away, while the hard setting includes up to p to 11 locations and any number of task-relevant and distractor objects.

### Coin Collector ("coin")
Agents frequently find tasks such as object search, environment navigation, or pick-and-place tasks challenging. The [Coin Collector](https://github.com/xingdi-eric-yuan/TextWorld-Coin-Collector) distills these into a single benchmark where an agent must explore a series of rooms to locate and pick up a single coin. In the original implementation, the game map typically takes the form of a connected loop or chain, such that continually moving to new locations means the agent will eventually discover the coin -- while including medium and hard modes that add in one or more "dead-end" paths.  To control for environment difficulty across games, the TextWorldExpress reimplementation uses the same map generator across environments, and generates arbitrary home environments rather than connected loops. The user maintains control of other measures of difficulty, including the total number of rooms, and the number of distractor objects placed in the environment.

### Map Reader ("mapreader")
The Map Reader environment requires agents to retrieve a coin from a particular location, and put it into the box found in the starting location. In contrast to Coin Collector, this environment provides a map of the environment that can be used by the agent to more efficiently navigate. The score is 0.5 for retrieving the coin, and 1.0 for placing the coin in the box at the start location. Task complexity can be controlled by varying the number of locations in the environment, the distance from the starting location and where the coin is located, and the number of distractor objects randomly placed in the environment that are not required for the task.

### Arithmetic ("arithmetic")
The Arithmetic environment requires agents to first solve a math problem, then to pick up the item with the same quantity as the math problem answer, and place it in the box. For example, the agent may read the math problem (“Take the bundle of objects that is equal to 3 multiplied by 6, and place
them in the box”), and must then perform the arithmetic then take 18 apples and place them in the answer box. Distractor objects are populated corresponding to performing the arithmetic incorrectly (for example, including 3 oranges, corresponding to subtracting 3 from 6, and 2 pears, corresponding to 6 divided by 3), with the constraint that results have to be positive integer values. The score is 0.5 for picking up the correct object, and 1.0 for completing the task successfully. At the moment, task complexity cannot be controlled yet.

### Sorting ("sorting")
The Sorting environment requires agents to pick objects and place them in an answer box one at a time based on order of increasing quantity. To add complexity to the game, quantities optionally include units (e.g. 5kg of copper, 8mg of steel, 2g of iron) across measures of volume, mass, or length. The score is the normalized proportion of objects sorted in the correct order, where perfect sorts receive a score of 1.0, and errors cause the score to revert to zero and the game to end. The number of objects to sort is between 3 and 5. At the moment, task complexity cannot be controlled yet.

### Simon Says ("simonsays")
The Simon Says environment is rather simple and it is mainly used as a sanity check for learning agents. The task is to repeat exactly the action requested of you. Task complexity can be controlled by varying the game length, the number of distractor actions, and whether the agent has to memorize the entire action sequence at its first step.

### Pecking Order ("peckingorder")
The Pecking Order environment is rather simple and it is mainly used as a sanity check for learning agents. The task is to read and follow the instructions found in the environment until game completion. At the moment, the task complexity cannot be controlled.

# Usage

### Typical Usage, and Valid Action Generation
Typical usage involves first initializing a game generator, then repeatedly generating and stepping through games.  Examples are provided in the /examples/ folder, with an example agent that chooses a random action at each step described below:

```python
import random
from textworld_express import TextWorldExpressEnv

# Initialize game generator
env = TextWorldExpressEnv(envStepLimit=100)

# Set the game generator to generate a particular game (cookingworld, twc, or coin)
env.load(gameName="twc", gameParams="numLocations=3,includeDoors=1")

# Then, randomly generate and play 10 games within the defined parameters
for episode_id in range(10):
  # First step
  obs, infos = env.reset(seed=episode_id, gameFold="train", generateGoldPath=True)

  # Display the observations from the environment.
  print(obs)

  for step_id in range(0, 50):
    # Select a random valid action
    validActions = sorted(infos['validActions'])
    randomAction = random.choice(validActions)

    # Take that action
    obs, reward, done, infos = env.step(randomAction)

    # Display action and the game's feedback.
    print(">", randomAction)
    print(obs)

```

### Setting Game Parameters
Environments initialize with default parameters.  To change the parameters, supply a comma-delimited string into `gameParams` when calling `env.load()`.  An example of a valid parameter configuration string for CookingWorld might be `numLocations=5, numIngredients=3, numDistractorItems=0, includeDoors=0, limitInventorySize=0`. Valid parameters are different for each environment, and include:

**CookingWorld:**
| Parameter      | Description | Valid range |
| ----------- | ----------- |  ----------- |
| numLocations        | The number of locations in the environment  | 1-11 (Default: 11) |
| numIngredients   | The number of ingredients to use in generating the random recipe         | 1-5 (Default: 3) |
| numDistractorItems   | The number of distractor ingredients (not used in the recipe) in the environment    | 0-10 (Default: 10) |
| includeDoors        | Whether rooms have doors that need to be opened    | 0 or 1 (Default: 1) |
| limitInventorySize  | Whether the size of the inventory is limited       | 0 or 1 (Default: 1) |

**TextWorld Common Sense:**
| Parameter      | Description | Valid range |
| ----------- | ----------- |  ----------- |
| numLocations        | The number of locations in the environment  | 1-3 (Default: 3) |
| numItemsToPutAway   | The number of items to put away             | 1-10 (Default: 4) |
| includeDoors        | Whether rooms have doors that need to be opened    | 0 or 1 (Default: 0) |
| limitInventorySize  | Whether the size of the inventory is limited       | 0 or 1 (Default: 0) |

**Coin Collector:**
| Parameter      | Description | Valid range |
| ----------- | ----------- |  ----------- |
| numLocations        | The number of locations in the environment  | 1-11 (Default: 11) |
| numDistractorItems  | The number of distractor (i.e. non-coin) items in the environment    | 0-10 (Default: 0) |
| includeDoors        | Whether rooms have doors that need to be opened    | 0 or 1 (Default: 1) |
| limitInventorySize  | Whether the size of the inventory is limited       | 0 or 1 (Default: 1) |

**Map Reader:**
| Parameter      | Description | Valid range |
| ----------- | ----------- |  ----------- |
| numLocations        | The number of locations in the environment  | 1-50 (Default: 15) |
| maxDistanceApart   | The number of locations to go through before finding the coin    | 1-8 (Default: 4) |
| maxDistractorItemsPerLocation   | The maximum number of distractor (i.e. non-coin) items per location  | 0-3 (Default: 3) |
| includeDoors        | Whether rooms have doors that need to be opened    | 0 or 1 (Default: 0) |
| limitInventorySize  | Whether the size of the inventory is limited       | 0 or 1 (Default: 0) |

**Arithmetic:**
This environment has no tweakable parameters yet.

**Sorting:**
This environment has no tweakable parameters yet.

**Simon Says:**
| Parameter      | Description | Valid range |
| ----------- | ----------- |  ----------- |
| gameLength      | The number of actions to repeat in order  | 1-1000 (Default: 5) |
| numDistractors  | The number of irrelevant actions    | 0-5 (Default: 3) |
| memorization    | Whether the entire sequence of actions is shown at the first step (and only then)     | 0 or 1 (Default: 0) |
| verbose         | Whether positive feedback is provided after each successful action (only used with memorization) | 0 or 1 (Default: 0) |

**Pecking Order:**
This environment has no tweakable parameters yet.

**Querying current game parameters:** Sometimes you may want to know what parameters the current game is generated with.  These can be queried using the `getGenerationProperties()` method:
```python
print("Generation properties: " + str(env.getGenerationProperties()))
```


### Gold paths

Gold paths can be generated by setting the `generateGoldPath` flag to be `true` when using `reset()`.  The path itself can be retrieved using the `env.getGoldActionSequence()` method:

```python
print("Gold path: " + str(env.getGoldActionSequence()))
```

Note that the gold paths are generated by agents that generally perform random walks in the environment, so while they lead to successful task completion, they may not be the shortest/most efficient paths.  For example, this path for Text World Common Sense wanders the environment until it either sees an object to pick up (e.g. take white coat), or an appropiate container to put an object in (e.g. put white coat in wardrobe):

> Gold path: ['look around', 'move west', 'take white coat', 'take brush', 'open wardrobe', 'put white coat in wardrobe', 'move east', 'move west', 'move east', 'move west', 'move east', 'move west', 'move east', 'move north', 'take eyeliner', 'take plaid blanket', 'put eyeliner in dressing table', 'open bathroom cabinet', 'put brush in bathroom cabinet', 'move south', 'move north', 'move south', 'move west', 'open chest of drawers', 'put plaid blanket in chest of drawers', 'move east']

### Full State Space (On Demand)

For small, fully-explorable games (e.g. small `coin`/`mapreader` configurations used for teaching search algorithms like BFS/DFS/A*), you can ask the server to crawl and return the *entire* reachable state graph from wherever the environment currently is -- typically right after `reset()`. This replaces having to separately pre-crawl and ship around per-seed JSON files: call it once per episode and get back the whole graph directly.

```python
from textworld_express import TextWorldExpressEnv

env = TextWorldExpressEnv(envStepLimit=100)
env.load(gameName="coin", gameParams="numLocations=5,includeDoors=1,numDistractorItems=0")
obs, infos = env.reset(seed=3, gameFold="train", generateGoldPath=True)

stateSpace = env.getFullStateSpace(maxNodes=50000, maxDepth=-1)
print(stateSpace["numStates"], "states,", stateSpace["numEdges"], "edges, truncated:", stateSpace["truncated"])
```

`stateSpace` has the shape:
```python
{
  "startId": "s0",
  "numStates": 96, "numEdges": 560, "truncated": False,
  "states": {
    "s0": {
      "observation": "...", "look": "...", "inventory": "...",
      "location": "kitchen",             # ground-truth room name; "" for games without room structure
      "validActions": ["move north", ...],
      "scoreRaw": 0.0, "score": 0.0,
      "taskSuccess": False, "taskFailure": False,
    },
    ...
  },
  "graph": [["s0", "move north", "s4"], ...],   # [fromId, action, toId] transitions
}
```

State identity is a fingerprint of the *entire* world (every room's contents and door states, not just the room the agent currently stands in, plus inventory and agent location) for games that support it (currently `coin`, `mapreader`); this matters because two states can look identical from the current room while differing in a room the agent isn't in (e.g. a door left open elsewhere), and treating those as the same state would silently corrupt search results. Games without this support fall back to a step-local signature (current look text + inventory + task status), which is only an approximation. `maxNodes` bounds how large a crawl is allowed to get (important for games where the state space is combinatorially large, e.g. `cookingworld`) -- if the cap is hit, `truncated` is `True` and the returned graph is a (still internally-consistent) subset.

For convenience, `FullyObservableTextWorldExpressEnv` (a drop-in subclass of `TextWorldExpressEnv`) automatically calls `getFullStateSpace()` on `reset()` and attaches the result to `infos['stateSpace']` on every subsequent `step()` as well (computed once per episode, not re-crawled every step). For the games that expose a ground-truth room name per state, it also derives `infos['roomMap']` (a list of `(room1, action, room2)` transitions) and `infos['roomCoordinates']` (`room -> (x, y)`, laid out via BFS from the start room) automatically; both are `None` for games without room-level structure.

```python
from textworld_express import FullyObservableTextWorldExpressEnv

env = FullyObservableTextWorldExpressEnv(envStepLimit=100, maxStateSpaceNodes=50000)
env.load(gameName="mapreader", gameParams="numLocations=5,includeDoors=1,maxDistanceApart=3,maxDistractorItemsPerLocation=0,limitInventorySize=0")
obs, infos = env.reset(seed=3, gameFold="train", generateGoldPath=True)

state_space = infos["stateSpace"]
room_map = infos["roomMap"]
room_coordinates = infos["roomCoordinates"]
```

### Incremental State Space (For Driving Your Own Search)

`getFullStateSpace()` crawls everything up front in one call, which is simple but pays the crawl cost regardless of whether a search algorithm actually needs most of it. `getInitialState()`/`getSuccessors()` instead let *you* drive the exploration one state at a time -- e.g. from inside your own BFS/DFS/A* implementation -- so the cost scales with how much of the space your search actually visits (a better heuristic means fewer calls).

Crucially, this is backed by a search session on the Java side that's entirely separate from the interactive session driven by `reset()`/`step()`: `getSuccessors()` never calls `step()` on the actual environment, so exploring the search space can't be conflated with actually playing the game (and stepping the live environment doesn't invalidate an in-progress search, either).

```python
from textworld_express import TextWorldExpressEnv

env = TextWorldExpressEnv(envStepLimit=100)
env.load(gameName="coin", gameParams="numLocations=5,includeDoors=1,numDistractorItems=0")
obs, infos = env.reset(seed=3, gameFold="train", generateGoldPath=True)

start_state = env.getInitialState(maxCacheSize=50000)
print(start_state["id"], start_state["location"], start_state["validActions"])

for successor in env.getSuccessors(start_state["id"]):
    print(successor["action"], "->", successor["state"]["id"], successor["state"]["location"])
```

`start_state` and each `successor["state"]` have the same shape as an entry of `getFullStateSpace()`'s `states` dict (see above), with an `id` field added. `getSuccessors(stateId)` requires `stateId` to have come from `getInitialState()` or a previous `getSuccessors()` call in the current search session (calling `getInitialState()` again starts a fresh session, discarding the old one); passing an unrecognized id raises `RuntimeError`. Revisiting an already-seen state (e.g. a self-loop action, or reaching the same state via a different path) returns that state's existing `id` rather than minting a new one, so a search algorithm's visited-set/dedup logic works the same way it would against `getFullStateSpace()`'s graph. `maxCacheSize` bounds the session the same way `maxNodes` bounds a full crawl.

If you only kept a state's `id` around (e.g. in a frontier list) without also stashing the dict it came with, `env.getStateInfo(stateId)` looks it up again -- a plain cache lookup, no extra `deepCopy()`/`step()` calls, so it's safe to call as often as you like. It only works for ids already known to the current search session (from `getInitialState()` or `getSuccessors()`), same restriction as `getSuccessors()`.

### Generating Pre-crawled Paths

One of the unique features of `TextWorldExpress` is that its performance is so fast, that it becomes possible to precrawl all possible actions that a hypothetical agent might take for a given game, out to some number of steps.  This has several main benefits and drawbacks:
- Positive: Game speed increases dramatically -- generally, as fast as traversing a tree using pointers.  In Scala, the single-thread performance for traversal has been benchmarked at 4-5 million steps per second.
- Negative: It takes some initial time to precrawl the paths (one-time investment; generally minutes-to-hours)
- Negative: It takes time to load the paths at the start of each run (generally on the older of seconds-to-minutes)
- Negative: It can take a lot of space to store precrawled paths (generally up to 1GB per game/seed, for trees of approximately 10-12 steps, depending on the game)
- Negative: There is a limited step horizon -- once the agent goes past the number of steps precrawled, there is no more information to provide.  For this reason it's important to precrawl only games that are small enough to solve within the number of steps that you precrawl.

Generally, if you are using less than a few dozen game variations during training, and you are using games that can be solved in under 10-12 steps, then path precrawling might be a way to gain dramatic benefits in performance.

To precrawl paths, use the path precrawling tool, `PathCrawler`:

    java -Xmx8g -cp textworld_express/textworld-express-1.0.0.jar textworldexpress.pathcrawler.PathPrecrawler twc train 0 8 numLocations=1,includeDoors=0,numItemsToPutAway=2

(Note that you may need to supply more than `8g` of memory, depending on the size of the path being crawled.)

The arguments (in order) are the `gameName`, `gameFold`, `seed`, `maximum depth to crawl the game state tree`, and `game generation properties string`.  The path crawler will export a large JSON file as output.  To load these precrawled paths in Python, please check the `precrawledPathReader.py` example.  For Java/Scala, please see `textworldexpress.benchmark.BenchmarkPrecrawledPath` as an end-to-end example, where `textworldexpress.pathcrawler.PrecrawledPath` provides a storage class for loading/saving precrawled paths (as well as quickly finding winning paths).  Path nodes are stored internally as string-hashed storage classes (`PrecrawledNode` and `StepResultHashed`) for speed/storage efficiency, where `StepResultHashed` can be quickly converted into the normal, human-readable, unhashed version using the `StepResultHashed.toStepResult()` method.  Several example precrawled paths (which are used for the benchmarking scripts) are provided in `precrawledpaths.zip`.

Path crawling can generate large files.  Before path crawling, you'll likely want to make sure that the game is sized appropriately so that it can be solved within the number of steps given.  Usually, this means limiting the number of locations, number of task items, etc.  Below are example times and crawl sizes for a Text World Common Sense game generated with the following parameters (`numItemsToPutAway=2, numLocations=3, includeDoors=0, limitInventorySize=0`) on a 16-core machine:
| Depth      | Crawl Time | Number of Nodes |
| ----------- | ----------- |  ----------- |
7 | 2 sec | 198k |
8 | 23 sec | 1.6M |
9 | 209 sec | 13.5M |

# Benchmarks

### Python Benchmarks
For online generation mode:

    python examples/random_agent_speed_test.py --game-name=cookingworld --max-steps=50 --num-episodes=10000

For precrawled path mode (note this demo uses precrawled paths provided for benchmarking in the repository):

    unzip precrawledpaths.zip
    python examples/precrawledPathReader.py

### Scala Benchmarks
For online generation mode (argument should be one of cookingworld, twc, or coin):

    java -Xmx4g -cp textworld_express/textworld-express-1.0.0.jar textworldexpress.benchmark.BenchmarkOnline coin

For precrawled path mode (single-threaded, note thishis demo uses precrawled paths provided for benchmarking in the repository.

    java -Xmx4g -cp textworld_express/textworld-express-1.0.0.jar textworldexpress.benchmark.BenchmarkPrecrawledPath

For extra speed, a threaded precrawled path benchmark (where here, change `32` to the desired number of threads):

    java -Xmx4g -cp textworld_express/textworld-express-1.0.0.jar textworldexpress.benchmark.BenchmarkPrecrawledPathThreaded 32


# Frequently Asked Questions
**Q: Why is the Python version 10x slower than the Java/Scala version?**
A: This partially due to the `py4j` binders, that allow interfacing Python to Java/Scala code through sockets.  We will look for faster solutions in the future, though the Python interface to `TextWorldExpress` is still about 100 times faster than the original TextWorld, so it is still a big win.

**Q: Will there be more benchmark games added/I want to add my own benchmark game to TextWorldExpress**
A: One of the main ways that TextWorldExpress gets its speed is through essentially hardcoding the games, mechanics, and (particularly) the valid action generation.  To implement your own games, please use the existing games as templates, and open a github issue if you run into any issues.  If you would like to recommend a new game to add to TextWorldExpress, please make a feature request in the github issues.

**Q: What is the fastest TextWorldExpress can run?**
A: The fastest we have clocked `TextWorldExpress` using the random agent benchmark is 4-5 million steps/sec per thread using precrawled games and the Scala native API, with multi-threaded performance at approximately 34 million steps/sec using an AMD 3950X 16-core CPU with 32 threads.  This is equivalent to about 2 billion steps per minute.  2 billion steps would take a single thread of the original TextWorld about 77 days to run.


# Citation
If you use `TextWorldExpress`, please provide the following citation:
```
@article{jansen2022textworldexpress,
  url = {https://arxiv.org/abs/2208.01174},
  author = {Jansen, Peter A. and Côté, Marc-Alexandre},
  title = {TextWorldExpress: Simulating Text Games at One Million Steps Per Second},
  journal = {arXiv},
  year = {2022},
}
```
