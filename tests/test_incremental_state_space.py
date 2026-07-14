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
    assert state["taskSuccess"] is False


def test_successors_match_valid_actions():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState()
    successors = env.getSuccessors(state["id"])
    assert {s["action"] for s in successors} == set(state["validActions"])
    for s in successors:
        assert "id" in s["state"]


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
    for action in goldPath:
        successors = env.getSuccessors(currentId)
        match = next(s for s in successors if s["action"] == action)
        currentId = match["state"]["id"]
    assert match["state"]["taskSuccess"] is True

    # Expand further *past* the goal state -- this used to raise via a malformed "Infinity" in
    # the JSON payload (orjson.loads would fail to parse it).
    for successor in env.getSuccessors(currentId):
        assert math.isfinite(successor["state"]["score"])
        assert math.isfinite(successor["state"]["scoreRaw"])


def test_gold_path_reachable_via_incremental_expansion():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train", generateGoldPath=True)
    goldPath = env.getGoldActionSequence()

    state = env.getInitialState()
    currentId = state["id"]
    finalState = None
    for action in goldPath:
        successors = env.getSuccessors(currentId)
        match = [s for s in successors if s["action"] == action]
        assert len(match) == 1, f"action {action!r} not offered from state {currentId}"
        finalState = match[0]["state"]
        currentId = finalState["id"]

    assert finalState["taskSuccess"] is True


def test_revisiting_a_state_returns_the_same_id():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    start = env.getInitialState()
    successors = env.getSuccessors(start["id"])
    moveBack = next(s for s in successors if s["action"] == "look around")
    # "look around" is a self-loop -- it shouldn't mint a new state id.
    assert moveBack["state"]["id"] == start["id"]


def test_unknown_state_id_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")
    env.getInitialState()

    with pytest.raises(RuntimeError):
        env.getSuccessors("not-a-real-id")


def test_get_successors_without_initial_state_raises():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    with pytest.raises(RuntimeError):
        env.getSuccessors("s0")


def test_get_state_info_looks_up_without_expanding():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    start = env.getInitialState()
    successors = env.getSuccessors(start["id"])
    someSuccessorId = successors[0]["state"]["id"]

    # Re-fetch by id alone (as if we'd only kept the id, not the dict) and confirm it matches.
    refetched = env.getStateInfo(someSuccessorId)
    assert refetched == successors[0]["state"]

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
    frontier = [state["id"]]
    for _ in range(3):
        nextFrontier = []
        for stateId in frontier:
            for successor in env.getSuccessors(stateId):
                nextFrontier.append(successor["state"]["id"])
        frontier = nextFrontier

    # The live session's run history/move count must be unaffected by all that searching.
    assert env.getNumSteps() == 1  # just the initial reset() entry
    obs_after, _, _, _ = env.step("look around")
    assert obs_after == obs


def test_truncation():
    env = TextWorldExpressEnv()
    env.load(gameName="coin", gameParams=COIN_PARAMS)
    env.reset(seed=3, gameFold="train")

    state = env.getInitialState(maxCacheSize=2)
    successors = env.getSuccessors(state["id"])
    # With such a tiny cache, not every action can mint a new state.
    ids = {s["state"]["id"] for s in successors}
    assert len(ids) <= 2
