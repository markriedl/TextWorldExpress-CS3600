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
    assert finalState["taskSuccess"] is True


def test_full_state_space_gold_path_reachable_mapreader():
    env = TextWorldExpressEnv()
    env.load(gameName="mapreader", gameParams=MAPREADER_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    stateSpace = env.getFullStateSpace(maxNodes=200000)
    _assert_internally_consistent(stateSpace)
    finalState = _gold_path_final_state(stateSpace, goldPath)
    assert finalState["taskSuccess"] is True

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
