package textworldexpress.statespace

import textworldexpress.struct.{StepResult, TextGame}

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer

/*
 * A persistent, incrementally-expandable cache of states for one search session, entirely
 * decoupled from any interactive/live TextWorldExpressEnv session -- reset()/expand() never touch
 * the game passed into reset(), and nothing here is reachable through env.step()/env.reset(), so a
 * search algorithm driving this can't accidentally conflate its own exploration with actually
 * playing the game.
 *
 * This is the shared engine behind both StateSpaceCrawler (which drives it to exhaustion internally
 * for the one-shot getFullStateSpace() call) and PythonInterface's getInitialState()/getSuccessors()
 * (which instead let the *caller* -- e.g. a student's search algorithm -- decide what to expand and
 * when, one state at a time).
 *
 * State identity prefers TextGame.getWorldStateSignature() (a fingerprint of the *whole* world),
 * since two states can look identical from the current room (same freeLookStr/inventoryStr) while
 * differing in a room the agent isn't currently in (e.g. a door left open elsewhere) -- collapsing
 * those into one node would silently merge genuinely different states. For games that don't
 * implement getWorldStateSignature() (it returns ""), we fall back to the step-local signature
 * (look/inventory/task status); that's only an approximation, but still much better than nothing.
 */
class IncrementalStateSpace(val maxCacheSize:Int) {
  // Publicly readable so callers (StateSpaceCrawler, PythonInterface) can look up node details.
  val nodes = mutable.LinkedHashMap[String, StateNode]()
  var truncated = false

  private val games = mutable.Map[String, TextGame]()
  private val sigToId = mutable.Map[String, String]()
  private var nextIdNum = 0

  private def signature(game:TextGame, sr:StepResult):String = {
    val worldSig = game.getWorldStateSignature()
    if (worldSig.nonEmpty) worldSig
    else sr.freeLookStr + "|" + sr.inventoryStr + "|" + sr.taskSuccess + "|" + sr.taskFailure
  }

  private def nextId():String = {
    val id = "s" + nextIdNum
    nextIdNum += 1
    id
  }

  private def mkNode(id:String, game:TextGame, sr:StepResult):StateNode = {
    new StateNode(
      id = id,
      observation = sr.observationStr,
      look = sr.freeLookStr,
      inventory = sr.inventoryStr,
      location = game.getLocationName(),
      validActions = sr.validActions,
      scoreRaw = sr.scoreRaw,
      scoreNormalized = sr.scoreNormalized,
      taskSuccess = sr.taskSuccess,
      taskFailure = sr.taskFailure
    )
  }

  // (Re)initializes this state space from a live game/step result -- e.g. whatever `this.game`/
  // `this.curStepResult` currently are in PythonInterface, typically right after reset(). Discards
  // any previously-cached search. startGame is deep-copied immediately, so the caller's live
  // game/session is never mutated by a later expand().
  def reset(startGame:TextGame, startStepResult:StepResult):StateNode = {
    nodes.clear()
    games.clear()
    sigToId.clear()
    nextIdNum = 0
    truncated = false

    val sig = signature(startGame, startStepResult)
    val id = nextId()
    sigToId(sig) = id
    val node = mkNode(id, startGame, startStepResult)
    nodes(id) = node

    // deepCopy() doesn't preserve the mutable "last valid actions" bookkeeping used internally by
    // step(String) to resolve an action string -- initalStep() is the sanctioned, side-effect-free
    // way (used throughout this codebase, e.g. EntryPointPathCrawler) to regenerate it against the
    // clone's own (cloned) object graph before we branch off of it.
    val rootCopy = startGame.deepCopy()
    rootCopy.initalStep()
    games(id) = rootCopy

    node
  }

  // Expands one previously-seen state (by id) into its successors -- one action/deepCopy/step per
  // valid action from that state, deduped against every state seen so far in this session (so
  // re-discovering an already-known state via a different action returns that same id rather than
  // minting a new one). Returns None if `stateId` was never returned by reset() or expand() in this
  // session (e.g. a stale id from a previous reset()).
  def expand(stateId:String):Option[Array[(String, String)]] = {
    val cachedGame = games.get(stateId)
    if (cachedGame.isEmpty) return None

    val curNode = nodes(stateId)
    val edges = new ArrayBuffer[(String, String)]()  // (action, toId)

    for (action <- curNode.validActions if !truncated) {
      val gameCopy = cachedGame.get.deepCopy()
      gameCopy.initalStep()
      val sr = gameCopy.step(action)
      val sig = signature(gameCopy, sr)

      sigToId.get(sig) match {
        case Some(existingId) =>
          edges.append((action, existingId))
        case None =>
          if (nodes.size >= maxCacheSize) {
            truncated = true
          } else {
            val newId = nextId()
            sigToId(sig) = newId
            nodes(newId) = mkNode(newId, gameCopy, sr)
            games(newId) = gameCopy
            edges.append((action, newId))
          }
      }
    }

    Some(edges.toArray)
  }
}
