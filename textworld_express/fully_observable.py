from textworld_express.textworld_express import TextWorldExpressEnv


# Cardinal-direction offsets used to lay movement-connected rooms out on a 2D grid.
_DIRECTION_OFFSETS = {
    "move north": (0, 1),
    "move south": (0, -1),
    "move east": (1, 0),
    "move west": (-1, 0),
}


class FullyObservableTextWorldExpressEnv(TextWorldExpressEnv):
    """
    A TextWorldExpressEnv that also exposes the entire reachable state space in `infos`,
    computed on demand from the server right after reset() (see getFullStateSpace()).

    This replaces the old workflow of separately pre-crawling and shipping around per-seed
    JSON files: `infos['stateSpace']` is always available for whatever game/seed is currently
    loaded, with no extra setup required.

    `infos['stateSpace']` has the shape:
        {
          "startId": str,
          "numStates": int, "numEdges": int, "truncated": bool,
          "states": {id: {"observation", "look", "inventory", "location",
                          "validActions", "scoreRaw", "score",
                          "taskSuccess", "taskFailure"}, ...},
          "graph": [[fromId, action, toId], ...],
        }

    For games that expose a ground-truth room name per state (currently "coin" and
    "mapreader"), `infos['roomMap']` (a list of (room1, action, room2) transitions) and
    `infos['roomCoordinates']` (room -> (x, y), laid out via BFS from the start room) are
    also derived automatically. Both are None for games without room-level structure.

    Set `autoCrawlStateSpace=False` (or flip `env.autoCrawlStateSpace` at any point) if you're
    instead driving search yourself via getInitialState()/getSuccessors()/getStateInfo() -- that
    skips the full crawl on every reset() (infos['stateSpace']/roomMap/roomCoordinates will be
    None), since a search built on those incremental calls doesn't need it materialized up front.
    """

    def __init__(self, serverPath=None, envStepLimit=100, maxStateSpaceNodes=50000, maxStateSpaceDepth=-1, computeRoomLayout=True, autoCrawlStateSpace=True):
        super().__init__(serverPath=serverPath, envStepLimit=envStepLimit)
        self.maxStateSpaceNodes = maxStateSpaceNodes
        self.maxStateSpaceDepth = maxStateSpaceDepth
        self.computeRoomLayout = computeRoomLayout
        # If you're driving search yourself via getInitialState()/getSuccessors()/getStateInfo()
        # instead of using infos['stateSpace'], turn this off (env.autoCrawlStateSpace = False) --
        # otherwise every reset() pays for a full crawl that the search never uses.
        self.autoCrawlStateSpace = autoCrawlStateSpace

        self._stateSpace = None
        self._roomMap = None
        self._roomCoordinates = None

    def reset(self, seed=None, gameFold=None, gameName=None, gameParams=None, generateGoldPath=False):
        obs, infos = super().reset(seed=seed, gameFold=gameFold, gameName=gameName, gameParams=gameParams, generateGoldPath=generateGoldPath)

        # The state space is invariant for the rest of the episode, so compute it once here
        # rather than on every step().
        if self.autoCrawlStateSpace:
            self._stateSpace = self.getFullStateSpace(self.maxStateSpaceNodes, self.maxStateSpaceDepth)
            if self.computeRoomLayout:
                self._roomMap, self._roomCoordinates = self._computeRoomLayout(self._stateSpace)
            else:
                self._roomMap, self._roomCoordinates = None, None
        else:
            self._stateSpace, self._roomMap, self._roomCoordinates = None, None, None

        self._attachStateSpace(infos)
        return obs, infos

    def step(self, inputStr: str):
        obs, reward, done, infos = super().step(inputStr)
        self._attachStateSpace(infos)
        return obs, reward, done, infos

    def _attachStateSpace(self, infos):
        infos["stateSpace"] = self._stateSpace
        infos["roomMap"] = self._roomMap
        infos["roomCoordinates"] = self._roomCoordinates

    @staticmethod
    def _computeRoomLayout(stateSpace):
        states = stateSpace["states"]

        # Room-to-room transitions, derived from "move <direction>" edges between states whose
        # ground-truth `location` differs. Games without room-level location info (games["location"]
        # is always "") simply produce no transitions here.
        transitions = set()
        movesFrom = {}
        for fromId, action, toId in stateSpace["graph"]:
            if not action.startswith("move "):
                continue
            fromRoom = states[fromId]["location"]
            toRoom = states[toId]["location"]
            if not fromRoom or not toRoom or fromRoom == toRoom:
                continue
            transitions.add((fromRoom, action, toRoom))
            movesFrom.setdefault(fromRoom, {})[action] = toRoom

        if not movesFrom:
            return None, None

        startRoom = states[stateSpace["startId"]]["location"]
        coordinates = {startRoom: (0, 0)}
        frontier = [startRoom]
        while frontier:
            nextFrontier = []
            for room in frontier:
                x, y = coordinates[room]
                for action, neighbor in movesFrom.get(room, {}).items():
                    if neighbor in coordinates:
                        continue
                    dx, dy = _DIRECTION_OFFSETS.get(action, (0, 0))
                    coordinates[neighbor] = (x + dx, y + dy)
                    nextFrontier.append(neighbor)
            frontier = nextFrontier

        return sorted(transitions), coordinates
