import java.lang.instrument.Instrumentation;
import java.nio.file.*;
public class PositionAgent {
 public static void agentmain(String directory, Instrumentation instrumentation) throws Exception {
  Object game = Class.forName("aTx").getMethod("cWt").invoke(null);
  Object player = game.getClass().getMethod("cWv").invoke(game);
  Class<?> type = player.getClass();
  String name = String.valueOf(type.getMethod("getName").invoke(player));
  Object x = type.getMethod("getWorldX").invoke(player);
  Object y = type.getMethod("getWorldY").invoke(player);
  Object z = type.getMethod("getAltitude").invoke(player);
  String json = String.format("{\"time\":\"%s\",\"name\":\"%s\",\"x\":%s,\"y\":%s,\"z\":%s}%n",java.time.Instant.now(), name.replace("\"","\\\""),x,y,z);
  Files.writeString(Path.of(directory,"player-position.json"),json);
  Files.writeString(Path.of(directory,"player-positions.jsonl"),json,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
 }
}
