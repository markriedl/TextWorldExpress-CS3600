package textworldexpress.runtime

import java.io.PrintWriter

import py4j.GatewayServer
import textworldexpress.generator.GameGenerator
import textworldexpress.JSON
import textworldexpress.statespace.{IncrementalStateSpace, StateSpaceCrawler, StateSpaceResult}
import textworldexpress.struct.{StepResult, TextGame}

import collection.JavaConverters._
import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer


class PythonInterface() {
  val ERROR_MESSAGE_UNINITIALIZED = "ERROR: Interface is not initialized -- call reset() before beginning."
  var errorStr:String = ""

  // Game and gold path
  var gameGenerator:GameGenerator = null
  var game:TextGame = null
  var goldPath:Array[String] = Array.empty[String]
  var properties:Map[String, Int] = Map[String, Int]()
  var curStepResult:StepResult = null

  // A separate, incrementally-expandable search space, entirely decoupled from `game`/
  // `curStepResult` above -- see getInitialStateJSON()/getSuccessorsJSON(). Deliberately not reset
  // by load()/step(), so that calling those to drive the interactive session doesn't invalidate an
  // in-progress search (and vice versa: expanding the search space never calls step() on `game`).
  var searchSpace:IncrementalStateSpace = null

  /*
   * Load/reset/shutdown server
   */
  def load(gameName:String, paramStr:String):String = {
    // Clear variables
    this.game = null
    this.goldPath = Array.empty[String]
    this.errorStr = ""
    this.curStepResult = null
    this.gameGenerator = null

    // Step 1: Parse any properties passed in through the string
    val (_props, propErrorStr) = PythonInterface.parseParamStr(paramStr)
    if (propErrorStr.length > 0) return errorStr
    this.properties = _props

    // Step 2: Create the Game Generator
    val (success, gameGenerator) = GameGenerator.mkGameGenerator(gameName, this.properties)
    if (!success) {
      println ("ERROR creating Game Generator: ")
      println (gameGenerator.errorStr)
      errorStr = gameGenerator.errorStr
      return errorStr
    }
    this.gameGenerator = gameGenerator
    return ""
  }

  def loadAndMake(gameName:String, gameFold:String, seed:Int, paramStr:String, generateGoldPath:Boolean):StepResult = {
    // Step 1: Parse any properties passed in through the string
    // Step 2: Create the Game Generator
    val errMsg = this.load(gameName, paramStr)
    if (errMsg != "") return StepResult.mkErrorMessage(errMsg)

    // Step 3: Generate new game
    return this.generateNewGame(seed, gameFold, generateGoldPath)
  }

  // Mirror with JSON output
  def loadJSON(gameName:String, gameFold:String, seed:Int, paramStr:String, generateGoldPath:Boolean):String = {
    val stepResult = this.loadAndMake(gameName, gameFold, seed, paramStr, generateGoldPath)
    stepResult.toJSON()
  }


  // Assumes that load() has already been called, and gameGenerator is valud.
  def generateNewGame(seed:Int, gameFold:String, generateGoldPath:Boolean):StepResult = {
    if (this.gameGenerator == null) {
      errorStr = "ERROR: Game generator is not initialized.  Call load() before attempting to generate new games."
      return StepResult.mkErrorMessage(errorStr)
    }

    // Generate new game
    if (generateGoldPath) {
      // With gold path
      val (_game, _goldPath) = this.gameGenerator.mkGameWithGoldPath(seed, gameFold)
      this.game = _game
      this.goldPath = _goldPath

      // Check gold path is present
      if (goldPath.length == 0) this.errorStr = "ERROR: Unable to generate gold path."
    } else {
      // Without gold path
      this.game = this.gameGenerator.mkGame(seed, gameFold)
    }

    // Take first 'step'
    this.curStepResult = game.initalStep()
    return this.curStepResult
  }

  // Mirror with JSON output
  def generateNewGameJSON(seed:Int, gameFold:String, generateGoldPath:Boolean):String = {
    val stepResult = this.generateNewGame(seed, gameFold, generateGoldPath)
    stepResult.toJSON()
  }


  def resetWithRandomSeed(gameFold:String, generateGoldPath:Boolean):StepResult = {
    // Step 1: Create random seed according to fold
    var randSeed = -1
    gameFold match {
      case "train" => randSeed = this.getRandomSeedTrain()
      case "dev" => randSeed = this.getRandomSeedDev()
      case "test" => randSeed = this.getRandomSeedTest()
      case _ => {
        this.errorStr = "ERROR: Unknown game fold (" + gameFold + ").  Valid options are (train, dev, test)."
        return StepResult.mkErrorMessage(this.errorStr)
      }
    }

    // Step 2: Generate new game
    return this.generateNewGame(seed = randSeed, gameFold, generateGoldPath)
  }

  // Mirror with JSON output
  def resetWithRandomSeedJSON(gameFold:String, generateGoldPath:Boolean):String = {
    val stepResult = this.resetWithRandomSeed(gameFold, generateGoldPath)
    stepResult.toJSON()
  }


  // Shutdown server
  def shutdown(): Unit = {
    sys.exit(0)
  }


  /*
   * Get valid tasks/environments
   */
  def getGameNames():java.util.List[String] = {
    GameGenerator.VALID_GAME_NAMES.toList.asJava
  }

  /*
   * Get generation properties
   */
  def getGenerationPropertiesJSON():String = {
    if (this.game == null) return "{}"

    val props = this.game.getGenerationProperties()

    val propStrs = new ArrayBuffer[String]
    for (propName <- props.keySet) {
      propStrs.append("\"" + propName + "\": " + props(propName))
    }

    return "{" + propStrs.mkString(", ") + "}"
  }

  /*
   * Get task description
   */
  def getTaskDescription():String = {
    if (this.game == null) return "Task description unavailable -- game is not initialized."

    return this.game.getTaskDescription()
  }

  def getObjectTree(path:String = ""):String = {
    if (this.game == null) return "Object tree unavailable -- game is not initialized. Call env.reset first."

    val objTree = this.game.getObjectTree()
    if (path == "") return objTree

    val pw = new PrintWriter(path)
    pw.print(objTree)
    pw.close()
    return ""
  }

  /*
   * Train/development/test sets
   */

  def getSeedsTrain():java.util.List[Int] = {
    return Range(0, 1000).toList.asJava
  }

  def getSeedsDev():java.util.List[Int] = {
    return Range(10000, 11000).toList.asJava
  }

  def getSeedsTest():java.util.List[Int] = {
    return Range(20000, 21000).toList.asJava
  }


  def getRandomSeedTrain():Int = {
    val randSeed = scala.util.Random.nextInt(1000) + 0
    return randSeed
  }

  def getRandomSeedDev():Int = {
    val randSeed = scala.util.Random.nextInt(1000) + 10000
    return randSeed
  }

  def getRandomSeedTest():Int = {
    val randSeed = scala.util.Random.nextInt(1000) + 20000
    return randSeed
  }


  /*
   * Gold action sequence
   */
  def getGoldActionSequence():java.util.List[String] = {
    return this.goldPath.toList.asJava
  }


  /*
   * Take action steps and get observations/scores
   */

  def getCompleted():Boolean = {
    if (this.curStepResult == null) return true
    if (this.curStepResult.taskSuccess || this.curStepResult.taskFailure) return true

    // Otherwise
    return false
  }

  // Normal
  def step(userInputString:String):StepResult = {
    // Error checking
    if (this.errorStr != "") return StepResult.mkErrorMessage(this.errorStr)
    if (this.game == null) return StepResult.mkErrorMessage(this.ERROR_MESSAGE_UNINITIALIZED)

    // Sanitize user input
    val userInputSanitized = userInputString.trim

    // Check for valid action
    if (!this.curStepResult.validActions.contains(userInputSanitized)) {
      return StepResult.mkInvalidStep(this.curStepResult)
    }

    // Take step
    this.curStepResult = game.step(userInputSanitized)

    // Return
    return this.curStepResult
  }

  // Mirror with JSON output
  def stepJSON(userInputString:String):String = {
    val stepResult = this.step(userInputString)
    stepResult.toJSON()
  }


  /*
   * Full state space (on demand)
   */

  // Crawls the entire reachable state graph from wherever the interactive session currently is
  // (typically called right after reset()). Never disturbs the live session -- the crawl operates
  // on a deep copy of `game`. maxDepth < 0 means unlimited depth.
  def getFullStateSpaceJSON(maxNodes:Int, maxDepth:Int):String = {
    if (this.errorStr != "") return StateSpaceResult.mkError(this.errorStr).toJSON()
    if (this.game == null) return StateSpaceResult.mkError(this.ERROR_MESSAGE_UNINITIALIZED).toJSON()

    val result = StateSpaceCrawler.crawl(this.game, this.curStepResult, maxNodes, maxDepth)
    result.toJSON()
  }


  /*
   * Incremental state space (for search algorithms to drive one expansion at a time, e.g. a
   * student's own BFS/DFS/A* -- as opposed to getFullStateSpaceJSON() above, which crawls
   * everything internally in one call). Backed by `searchSpace`, which is completely separate from
   * `game`/`curStepResult`: expanding search states here never calls step() on the interactive
   * session, so a search algorithm built on this can't accidentally conflate its own exploration
   * with actually playing the game.
   */

  // (Re)starts a search session from wherever the interactive session currently is (typically
  // called right after reset()). Returns the starting state. Never disturbs the live session.
  def getInitialStateJSON(maxCacheSize:Int):String = {
    if (this.errorStr != "") return PythonInterface.mkStateErrorJSON(this.errorStr)
    if (this.game == null) return PythonInterface.mkStateErrorJSON(this.ERROR_MESSAGE_UNINITIALIZED)

    this.searchSpace = new IncrementalStateSpace(maxCacheSize)
    val root = this.searchSpace.reset(this.game, this.curStepResult)
    "{\"error\":\"\",\"state\":" + root.toJSON() + "}"
  }

  // Expands one previously-seen state (by id, as returned by getInitialStateJSON()/this method) into
  // its successors. `stateId` must have come from getInitialStateJSON() or a previous call to this
  // method in the current search session (i.e. since the last getInitialStateJSON() call).
  def getSuccessorsJSON(stateId:String):String = {
    if (this.searchSpace == null) {
      return PythonInterface.mkSuccessorsErrorJSON("ERROR: No search in progress -- call getInitialState() first.")
    }

    this.searchSpace.expand(stateId) match {
      case None =>
        PythonInterface.mkSuccessorsErrorJSON("ERROR: Unknown state id (" + stateId + "). It must come from getInitialState(), or from getSuccessors() in the current search session.")
      case Some(successors) =>
        val entries = new ArrayBuffer[String]()
        for ((action, toId) <- successors) {
          entries.append("{\"action\":\"" + JSON.sanitize(action) + "\",\"state\":" + this.searchSpace.nodes(toId).toJSON() + "}")
        }
        "{\"error\":\"\",\"truncated\":" + this.searchSpace.truncated + ",\"successors\":[" + entries.mkString(",") + "]}"
    }
  }

  // Looks up a previously-seen state's info by id, without expanding it (no deepCopy/step -- just a
  // cache lookup). Useful when a search algorithm only kept an id around (e.g. in a frontier list)
  // without also stashing the state dict it came with.
  def getStateInfoJSON(stateId:String):String = {
    if (this.searchSpace == null) {
      return PythonInterface.mkStateErrorJSON("ERROR: No search in progress -- call getInitialState() first.")
    }

    this.searchSpace.nodes.get(stateId) match {
      case None =>
        PythonInterface.mkStateErrorJSON("ERROR: Unknown state id (" + stateId + "). It must come from getInitialState(), or from getSuccessors() in the current search session.")
      case Some(node) =>
        "{\"error\":\"\",\"state\":" + node.toJSON() + "}"
    }
  }

}

object PythonInterface {

  /*
   * Helper functions
   */

  def mkStateErrorJSON(errorStr:String):String = {
    "{\"error\":\"" + JSON.sanitize(errorStr) + "\",\"state\":null}"
  }

  def mkSuccessorsErrorJSON(errorStr:String):String = {
    "{\"error\":\"" + JSON.sanitize(errorStr) + "\",\"truncated\":false,\"successors\":[]}"
  }

  // Parse a string of comma-delimited parameters into a Map.
  // Returns (output, errorStr).
  def parseParamStr(strIn:String):(Map[String, Int], String) = {
    val out = mutable.Map[String, Int]()

    // Step 1: Split on deliminter (",")
    val params = strIn.split(",").map(_.trim())
    for (paramStr <- params) {
      if (paramStr.length > 0) {
        val fields = paramStr.split("=").map(_.trim)
        if (fields.length == 0) return (out.toMap, "ERROR: Unable to parse field.")
        if (fields.length == 1) return (out.toMap, "ERROR: Unable to find value for parameter (" + fields(0) + ").")
        if (fields.length > 2)  return (out.toMap, "ERROR: Too many fields found (" + fields.mkString(" ") + ").  A comma is likely missing between fields, or there is an extra equals sign.")
        val paramName = fields(0)
        val paramValue = fields(1)
        var paramValueInt:Int = -1
        try {
          paramValueInt = paramValue.toInt
        } catch {
          case _:Throwable => { return (out.toMap, "ERROR: Unable to parse parameter (" + paramName + ") value (" + paramValue + ") into an integer.")}
        }

        // Store
        out(paramName) = paramValueInt
      }
    }

    return (out.toMap, "")
  }

  def printUsage(): Unit = {
    println("Usage: PythonInterface <portNumber>")
  }

  def main(args:Array[String]): Unit = {
    println ("Initializing TextWorldExpress Python Server...")
    val obj = new PythonInterface()

    // Parse command line argument for port
    var port:Int = 25335      // Default port (if not specified)
    if (args.length == 1) {
      try {
        port = args(0).toInt
      } catch {
        case e:Throwable => {
          printUsage()
          throw new RuntimeException("ERROR: Unable to parse port number into integer(" + args(0) + ").")
        }
      }
    } else if (args.length > 1) {
      printUsage()
      sys.exit(1)
    }

    println ("Starting server on port " + port + ".")

    val server = new GatewayServer(obj, port)
    server.start()

    println ("Server started... ")

  }

}
