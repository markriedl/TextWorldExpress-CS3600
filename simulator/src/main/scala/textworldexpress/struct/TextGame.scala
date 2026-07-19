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

  // Ground-truth JSON for *every* room's full contents -- not just the room the agent currently
  // stands in -- including door open/closed status and any containers' open/closed status and
  // (possibly nested) contents. This reuses FastObject/Room's own toJSON() serialization, so it's
  // exactly as complete as the engine's internal object model (e.g. it correctly reflects a
  // distractor item that happens to be inside a fridge, not just sitting directly in the room).
  // Default is an empty JSON object for games without room structure.
  def getAllRoomsJSON():String = {
    return "{}"
  }

  // Ground-truth list of item names currently in the agent's inventory -- as opposed to the
  // `inventoryStr` on StepResult, which is natural-language text meant for display. Default empty
  // for games without this support.
  def getInventoryItems():Array[String] = {
    return Array.empty[String]
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
