from textworld_express import TextWorldExpressEnv, FullyObservableTextWorldExpressEnv


COIN_PARAMS = "numLocations=5,includeDoors=1,numDistractorItems=0"
MAPREADER_PARAMS = "numLocations=5,includeDoors=1,maxDistanceApart=3,maxDistractorItemsPerLocation=0,limitInventorySize=0"


def _assert_internally_consistent(stateSpace):
    assert stateSpace["startId"] in stateSpace["states"]
    assert stateSpace["numStates"] == len(stateSpace["states"])
    assert stateSpace["numEdges"] == len(stateSpace["graph"])

    for edge in stateSpace["graph"]:
        assert isinstance(edge, tuple)
        fromId, action, toId = edge
        assert fromId in stateSpace["states"]
        assert toId in stateSpace["states"]
        assert action in stateSpace["states"][fromId]["validActions"]

    for state in stateSpace["states"].values():
        assert isinstance(state["rooms"], dict)
        assert isinstance(state["inventoryItems"], list)
        # Deliberately absent -- see StateNode's docstring in StateSpaceCrawler.scala: baking the
        # engine's own win/lose flags into every search-API state would tie every search to
        # whatever single objective the built-in game happens to define.
        assert "taskSuccess" not in state
        assert "taskFailure" not in state


def _find_object(rooms, name):
    """Recursively search every room's (possibly nested) contents for an object by name."""
    def _search(contents):
        if name in contents:
            return contents[name]
        for obj in contents.values():
            found = _search(obj.get("contents", {}))
            if found is not None:
                return found
        return None

    for room in rooms.values():
        found = _search(room["contents"])
        if found is not None:
            return found
    return None


def _gold_path_final_state(stateSpace, goldPath):
    adjacency = {}
    for fromId, action, toId in stateSpace["graph"]:
        adjacency.setdefault(fromId, {})[action] = toId

    current = stateSpace["startId"]
    for action in goldPath:
        assert action in adjacency.get(current, {}), \
            f"gold action {action!r} not reachable from state {current} ({stateSpace['states'][current]['location']!r})"
        current = adjacency[current][action]

    return stateSpace["states"][current]


def test_full_state_space_basic_consistency_coin():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)

    stateSpace = env.getFullStateSpace(maxNodes=200000)
    _assert_internally_consistent(stateSpace)
    assert stateSpace["truncated"] is False
    assert stateSpace["numStates"] > 1


def test_full_state_space_gold_path_reachable_coin():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    stateSpace = env.getFullStateSpace(maxNodes=200000)
    finalState = _gold_path_final_state(stateSpace, goldPath)
    assert "coin" in finalState["inventoryItems"]


def test_full_state_space_gold_path_reachable_mapreader():
    env = TextWorldExpressEnv()
    env.load(gameName="mapreader", gameParams=MAPREADER_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    stateSpace = env.getFullStateSpace(maxNodes=200000)
    _assert_internally_consistent(stateSpace)
    finalState = _gold_path_final_state(stateSpace, goldPath)
    # mapreader's win condition is the coin ending up *in the box*, not just in inventory --
    # find the box (wherever it is) via the ground-truth `rooms` tree and check its contents.
    box = _find_object(finalState["rooms"], "box")
    assert box is not None
    assert "coin" in box["contents"]

    # mapreader exposes ground-truth room names per state.
    locations = {s["location"] for s in stateSpace["states"].values()}
    assert "" not in locations
    assert len(locations) > 1


def test_full_state_space_truncation():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    stateSpace = env.getFullStateSpace(maxNodes=3)
    assert stateSpace["truncated"] is True
    assert stateSpace["numStates"] <= 3


def test_fully_observable_env_reset_and_step():
    env = FullyObservableTextWorldExpressEnv(maxStateSpaceNodes=200000)
    obs, infos = env.reset(seed=3, gameFold="train", gameName="coin", gameParams=COIN_PARAMS, generateGoldPath=True)

    assert infos["stateSpace"] is not None
    _assert_internally_consistent(infos["stateSpace"])
    assert infos["roomMap"] is not None
    assert infos["roomCoordinates"] is not None
    assert infos["roomCoordinates"][infos["stateSpace"]["states"][infos["stateSpace"]["startId"]]["location"]] == (0, 0)

    stateSpaceAfterReset = infos["stateSpace"]
    obs, reward, done, infos = env.step("look around")
    # The state space doesn't change mid-episode -- same object, not recomputed.
    assert infos["stateSpace"] is stateSpaceAfterReset


def test_fully_observable_env_room_layout_none_when_no_rooms():
    env = FullyObservableTextWorldExpressEnv(maxStateSpaceNodes=50000)
    obs, infos = env.reset(seed=3, gameFold="train", gameName="arithmetic", gameParams="")

    assert infos["stateSpace"] is not None
    assert infos["roomMap"] is None
    assert infos["roomCoordinates"] is None


def test_rooms_reflect_every_room_not_just_the_current_one():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    # We're only ever in one room at a time, but ground truth should cover all of them.
    assert set(state["rooms"].keys()) >= {state["location"]}
    assert len(state["rooms"]) > 1

    for roomName, room in state["rooms"].items():
        assert room["name"] == roomName
        assert isinstance(room["contents"], dict)
        # Doors (present or None) are nested inside each room's own JSON.
        for direction in ("doorNorth", "doorSouth", "doorEast", "doorWest"):
            assert direction in room


def test_room_coordinates_consistent_with_adjacency():
    """Each room's ground-truth (x, y) should agree with its locationNorth/South/East/West
    neighbors -- north is +y, east is +x -- so a heuristic can measure inter-room distance without
    ever having to explore the map to derive coordinates itself."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    rooms = state["rooms"]
    for name, room in rooms.items():
        assert isinstance(room["x"], int)
        assert isinstance(room["y"], int)
        if room["locationNorth"]:
            neighbor = rooms[room["locationNorth"]]
            assert (neighbor["x"], neighbor["y"]) == (room["x"], room["y"] + 1)
        if room["locationSouth"]:
            neighbor = rooms[room["locationSouth"]]
            assert (neighbor["x"], neighbor["y"]) == (room["x"], room["y"] - 1)
        if room["locationEast"]:
            neighbor = rooms[room["locationEast"]]
            assert (neighbor["x"], neighbor["y"]) == (room["x"] + 1, room["y"])
        if room["locationWest"]:
            neighbor = rooms[room["locationWest"]]
            assert (neighbor["x"], neighbor["y"]) == (room["x"] - 1, room["y"])


def test_room_coordinates_preserved_across_expansion():
    """Room coordinates are assigned once at generation time -- confirm deepCopy() (used on every
    getSuccessors() expansion) actually carries them over, rather than resetting to (0, 0)."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    coordsBefore = {name: (room["x"], room["y"]) for name, room in state["rooms"].items()}

    nextState = env.getSuccessors(state["id"], state["validActions"][0])
    coordsAfter = {name: (room["x"], room["y"]) for name, room in nextState["rooms"].items()}

    assert coordsBefore == coordsAfter


def test_rooms_captures_items_nested_inside_containers():
    """Distractor items in the coin game can be placed inside a container (e.g. a fridge or
    shelf) rather than directly in the room -- rooms must reflect that nesting, not just a flat
    top-level listing, or an item hidden inside a container would be invisible."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams="numLocations=4,includeDoors=1,numDistractorItems=1")
    env.reset(seed=1, gameFold="train")  # known to place "black pepper" inside the pantry's shelf

    state = env.getInitialState()
    shelf = state["rooms"]["pantry"]["contents"]["shelf"]
    assert "black pepper" in shelf["contents"]


def test_movable_items_are_never_trapped_behind_a_closed_container():
    """The agent has no action to open a closed container (e.g. a fridge or drawer) in the coin
    game, so any movable item placed inside one would be permanently unreachable. Every movable
    item must therefore only ever sit directly in a room, or inside a container that's open."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams="numLocations=5,includeDoors=1,numDistractorItems=4")

    def _assert_reachable(contents):
        for obj in contents.values():
            if obj["isMovable"]:
                pass  # reachable by construction: we only recurse into open containers below
            if obj["isContainer"] and not obj["isOpen"]:
                assert obj["contents"] == {}, f"{obj['name']} is closed but has contents"
            else:
                _assert_reachable(obj["contents"])

    for seed in range(20):
        env.reset(seed=seed, gameFold="train")
        state = env.getInitialState()
        for room in state["rooms"].values():
            _assert_reachable(room["contents"])


def test_inventory_items_updates_alongside_text_inventory():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    state = env.getInitialState()
    assert state["inventoryItems"] == []

    currentId = state["id"]
    finalState = None
    for action in goldPath:
        finalState = env.getSuccessors(currentId, action)
        currentId = finalState["id"]

    assert finalState["inventoryItems"] == ["coin"]
    assert "coin" in finalState["inventory"]  # the natural-language text form still agrees


def test_fully_observable_env_auto_crawl_can_be_disabled():
    env = FullyObservableTextWorldExpressEnv(autoCrawlStateSpace=False)
    obs, infos = env.reset(seed=3, gameFold="train", gameName="coin", gameParams=COIN_PARAMS)

    assert infos["stateSpace"] is None
    assert infos["roomMap"] is None
    assert infos["roomCoordinates"] is None

    # getFullStateSpace() and the incremental API still work on request, regardless of the flag.
    assert env.getFullStateSpace()["numStates"] > 1
    assert env.getInitialState()["id"] is not None

    # Flipping it back on takes effect on the next reset().
    env.autoCrawlStateSpace = True
    obs, infos = env.reset(seed=3, gameFold="train")
    assert infos["stateSpace"] is not None
