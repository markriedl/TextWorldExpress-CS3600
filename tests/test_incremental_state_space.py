import math

import pytest

from textworld_express import TextWorldExpressEnv


COIN_PARAMS = "numLocations=4,includeDoors=1,numDistractorItems=0"


def test_initial_state_matches_reset():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    obs, infos = env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    assert state["observation"] == obs
    assert set(state["validActions"]) == set(infos["validActions"])
    assert state["inventoryItems"] == []


def test_successors_match_valid_actions():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    for action in state["validActions"]:
        nextState = env.getSuccessors(state["id"], action)
        assert "id" in nextState


def test_score_stays_finite_after_expanding_a_post_pickup_state():
    """Regression test: cloning a CoinGame state where the coin is already in the agent's
    inventory (rather than sitting in a room) used to freeze the scorer's maxScore at 0 (it was
    computed eagerly, before the clone's inventory -- and thus the coin -- had been copied over),
    causing score = raw/0 = Infinity on any further expansion of that state."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    state = env.getInitialState()
    currentId = state["id"]
    nextState = None
    for action in goldPath:
        nextState = env.getSuccessors(currentId, action)
        currentId = nextState["id"]
    assert nextState["inventoryItems"] == ["coin"]

    # Expand further *past* the goal state -- this used to raise via a malformed "Infinity" in
    # the JSON payload (orjson.loads would fail to parse it).
    for action in nextState["validActions"]:
        pastGoalState = env.getSuccessors(currentId, action)
        assert math.isfinite(pastGoalState["score"])
        assert math.isfinite(pastGoalState["scoreRaw"])


def test_gold_path_reachable_via_incremental_expansion():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    state = env.getInitialState()
    currentId = state["id"]
    currentValidActions = state["validActions"]
    finalState = None
    for action in goldPath:
        assert action in currentValidActions, f"action {action!r} not offered from state {currentId}"
        finalState = env.getSuccessors(currentId, action)
        currentId = finalState["id"]
        currentValidActions = finalState["validActions"]

    assert finalState["inventoryItems"] == ["coin"]


def test_revisiting_a_state_returns_the_same_id():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    start = env.getInitialState()
    # "look around" is a self-loop -- it shouldn't mint a new state id.
    assert env.getSuccessors(start["id"], "look around")["id"] == start["id"]


def test_unknown_state_id_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")
    env.getInitialState()

    with pytest.raises(RuntimeError):
        env.getSuccessors("not-a-real-id", "look around")


def test_invalid_action_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    with pytest.raises(RuntimeError):
        env.getSuccessors(state["id"], "not a real action")


def test_get_successors_without_initial_state_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    with pytest.raises(RuntimeError):
        env.getSuccessors("s0", "look around")


def test_get_state_info_looks_up_without_expanding():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    start = env.getInitialState()
    someSuccessor = env.getSuccessors(start["id"], start["validActions"][0])

    # Re-fetch by id alone (as if we'd only kept the id, not the dict) and confirm it matches.
    refetched = env.getStateInfo(someSuccessor["id"])
    assert refetched == someSuccessor

    # Re-fetching the start state works too.
    assert env.getStateInfo(start["id"]) == start


def test_get_state_info_unknown_id_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")
    env.getInitialState()

    with pytest.raises(RuntimeError):
        env.getStateInfo("not-a-real-id")


def test_get_state_info_without_initial_state_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    with pytest.raises(RuntimeError):
        env.getStateInfo("s0")


def test_search_is_decoupled_from_live_session():
    """Expanding the search space must never advance the actual interactive episode."""
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    obs, infos = env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    # Drive several rounds of search expansion.
    frontier = [state]
    for _ in range(3):
        nextFrontier = []
        for frontierState in frontier:
            for action in frontierState["validActions"]:
                nextFrontier.append(env.getSuccessors(frontierState["id"], action))
        frontier = nextFrontier

    # The live session's run history/move count must be unaffected by all that searching.
    assert env.getNumSteps() == 1  # just the initial reset() entry
    obs_after, _, _, _ = env.step("look around")
    assert obs_after == obs


def test_truncation():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    # maxCacheSize=2 already counts the root state, so only one more genuinely new state can be
    # minted before further new-state expansions start raising.
    state = env.getInitialState(maxCacheSize=2)
    ids = {state["id"]}
    sawTruncationError = False
    for action in state["validActions"]:
        try:
            nextState = env.getSuccessors(state["id"], action)
            ids.add(nextState["id"])
        except RuntimeError as e:
            assert "cache is full" in str(e)
            sawTruncationError = True

    # With such a tiny cache, not every action can mint a new state.
    assert len(ids) <= 2
    assert sawTruncationError
