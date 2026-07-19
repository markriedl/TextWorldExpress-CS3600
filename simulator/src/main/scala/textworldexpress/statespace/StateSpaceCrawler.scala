package textworldexpress.statespace

import textworldexpress.JSON
import textworldexpress.struct.{StepResult, TextGame}

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer

// One node in the crawled state graph.
//
// Deliberately excludes the engine's own taskSuccess/taskFailure win/lose flags (unlike StepResult,
// which still carries them for the interactive env.step()/env.reset() session) -- those flags are
// tied to whatever single built-in objective a game happens to define (e.g. CoinGame's "is the coin
// in inventory"), and baking that into every search-API state would make it impossible for a search
// algorithm to target a different objective (e.g. "pick up the coin AND the knife") without new
// Scala-side game code. Callers instead compute their own is_goal() from `rooms`/`inventoryItems`.
case class StateNode(id:String, observation:String, look:String, inventory:String, location:String, validActions:Array[String], scoreRaw:Double, scoreNormalized:Double, rooms:String, inventoryItems:Array[String]) {
  def toJSON():String = {
    val os = new StringBuilder()
    os.append("{")
    os.append("\"id\":\"" + JSON.sanitize(id) + "\",")
    os.append("\"observation\":\"" + JSON.sanitize(observation) + "\",")
    os.append("\"look\":\"" + JSON.sanitize(look) + "\",")
    os.append("\"inventory\":\"" + JSON.sanitize(inventory) + "\",")
    os.append("\"location\":\"" + JSON.sanitize(location) + "\",")
    os.append("\"validActions\":[\"" + validActions.map(JSON.sanitize).mkString("\",\"") + "\"],")
    os.append("\"scoreRaw\":" + scoreRaw + ",")
    os.append("\"score\":" + scoreNormalized + ",")
    // `rooms` is already-serialized JSON (from FastObject/Room.toJSON()), so it's embedded as-is,
    // not sanitized/quoted like the plain string fields above.
    os.append("\"rooms\":" + rooms + ",")
    os.append("\"inventoryItems\":[" + inventoryItems.map(x => "\"" + JSON.sanitize(x) + "\"").mkString(",") + "]")
    os.append("}")
    os.toString()
  }
}

// The full crawled state graph for a game, from whatever state it was in when crawl() was called.
class StateSpaceResult(val startId:String, val states:mutable.LinkedHashMap[String, StateNode], val edges:ArrayBuffer[(String, String, String)], val truncated:Boolean, val errorStr:String = "") {
  def toJSON():String = {
    val os = new StringBuilder()
    os.append("{")
    os.append("\"error\":\"" + JSON.sanitize(errorStr) + "\",")
    os.append("\"startId\":\"" + JSON.sanitize(startId) + "\",")
    os.append("\"numStates\":" + states.size + ",")
    os.append("\"numEdges\":" + edges.size + ",")
    os.append("\"truncated\":" + truncated + ",")

    val stateEntries = new ArrayBuffer[String]()
    for ((id, node) <- states) {
      stateEntries.append("\"" + JSON.sanitize(id) + "\":" + node.toJSON())
    }
    os.append("\"states\":{" + stateEntries.mkString(",") + "},")

    val edgeEntries = new ArrayBuffer[String]()
    for ((fromId, action, toId) <- edges) {
      edgeEntries.append("[\"" + JSON.sanitize(fromId) + "\",\"" + JSON.sanitize(action) + "\",\"" + JSON.sanitize(toId) + "\"]")
    }
    os.append("\"graph\":[" + edgeEntries.mkString(",") + "]")

    os.append("}")
    os.toString()
  }
}

object StateSpaceResult {
  // Used when the interface hasn't been initialized (no game loaded) -- mirrors StepResult.mkErrorMessage().
  def mkError(errorStr:String):StateSpaceResult = {
    new StateSpaceResult(startId = "", states = mutable.LinkedHashMap[String, StateNode](), edges = new ArrayBuffer[(String, String, String)](), truncated = false, errorStr = errorStr)
  }
}

/*
 * Crawls the entire reachable state graph from a given game/state, on demand, over the existing
 * py4j link -- so callers don't need to pre-crawl and ship around external per-seed JSON files.
 *
 * This exhausts an IncrementalStateSpace (see that class for the actual cloning/dedup logic) via a
 * plain BFS driven internally, for callers that want the whole graph back in one call (e.g. for
 * rendering a map, or for small games where pre-materializing everything is cheap and simple).
 * PythonInterface.getInitialState()/getSuccessors() instead let the *caller* drive expansion one
 * state at a time against the same IncrementalStateSpace machinery.
 */
object StateSpaceCrawler {

  // startGame/startStepResult describe whatever state the caller is currently in (e.g. right after
  // reset(), or mid-episode). startGame is deep-copied immediately, so the caller's live game/session
  // is never touched by the crawl.
  def crawl(startGame:TextGame, startStepResult:StepResult, maxNodes:Int, maxDepth:Int):StateSpaceResult = {
    val space = new IncrementalStateSpace(maxNodes)
    val root = space.reset(startGame, startStepResult)

    val edges = new ArrayBuffer[(String, String, String)]()
    val visited = mutable.Set[String](root.id)
    val queue = mutable.Queue[(String, Int)]()
    queue.enqueue((root.id, 0))

    while (queue.nonEmpty && !space.truncated) {
      val (curId, depth) = queue.dequeue()
      val curNode = space.nodes(curId)

      // Expand purely on reachability/depth -- not on the engine's own taskSuccess/taskFailure
      // (deliberately not part of StateNode; see its docstring), since a caller-defined objective may
      // need states beyond whatever the built-in game considers "done".
      val shouldExpand = maxDepth < 0 || depth < maxDepth
      if (shouldExpand) {
        space.expand(curId) match {
          case Some(successors) =>
            for ((action, toId) <- successors) {
              edges.append((curId, action, toId))
              if (!visited.contains(toId)) {
                visited.add(toId)
                queue.enqueue((toId, depth + 1))
              }
            }
          case None =>
            // Shouldn't happen: curId always came from a previous reset()/expand() call above.
            throw new RuntimeException("StateSpaceCrawler: internal error, unknown state id (" + curId + ").")
        }
      }
    }

    new StateSpaceResult(startId = root.id, states = space.nodes, edges = edges, truncated = space.truncated)
  }

}
