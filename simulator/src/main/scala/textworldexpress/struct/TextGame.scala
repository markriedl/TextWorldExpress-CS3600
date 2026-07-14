package textworldexpress.struct

import textworldexpress.objects.{FastObject, Room}

import scala.collection.mutable.ArrayBuffer

abstract class TextGame {

  /*
   * Cloning
   */
  def deepCopy():TextGame

  /*
   * Properties
   */

  def getGenerationProperties():Map[String, Int]

  def getTaskDescription():String

  def getObjectTree():String = {
    return "{}"
  }

  // Ground-truth name of the room/location the agent currently occupies.
  // Default is empty for games without a notion of rooms (e.g. arithmetic, sorting).
  def getLocationName():String = {
    return ""
  }

  // A ground-truth fingerprint of the *entire* world (every room's contents/doors, inventory,
  // agent location), used by StateSpaceCrawler to tell two states apart. This must cover the
  // whole world, not just what's locally visible/described (freeLookStr only covers the room the
  // agent currently stands in), since e.g. a door left open in a room the agent isn't currently in
  // is still part of the true state and affects future behavior. Default is empty, signaling that
  // no such global view is available for this game -- callers should fall back to a step-local
  // signature (freeLook/inventory/task status), which is only an approximation.
  def getWorldStateSignature():String = {
    return ""
  }

  /*
   * History
   */
  def getHistory():ArrayBuffer[ActionHistory]

  /*
   * Scoring
   */
  def getScore():GameScore

  /*
   * Steps
   */

  def initalStep():StepResult

  def step(actionStr:String):StepResult

  def step(validActionIdx:Int):StepResult

  def step(actionStr: String, actionNumber: Int, actionParams: Array[FastObject]):StepResult

}
