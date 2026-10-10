import com.sun.tools.attach.VirtualMachine;
import java.io.IOException;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import javax.swing.SwingUtilities;

/**
 * Starts a bounded, read-only observer inside a running Wakfu client JVM.
 * It samples the actor's appearance, height override and native HMI stacks;
 * it never invokes a setter or changes client state.
 *
 * Launch: java --add-modules jdk.attach -cp observer.jar VerifyDragonVisualState
 *        <pid> <actor-id> <seconds> <output-jsonl>
 * Or use the same <actor-id>;<seconds>;<output-jsonl> argument as -javaagent.
 */
public final class VerifyDragonVisualState {
  private VerifyDragonVisualState() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 4) {
      throw new IllegalArgumentException("expected pid actor-id seconds output-jsonl");
    }
    Path source = Path.of(VerifyDragonVisualState.class.getProtectionDomain()
        .getCodeSource().getLocation().toURI());
    if (Files.isDirectory(source)) {
      throw new IllegalStateException("run from the packaged agent jar");
    }
    String pid = args[0];
    String actor = args[1];
    String seconds = args[2];
    String output = Path.of(args[3]).toAbsolutePath().toString();
    VirtualMachine vm = VirtualMachine.attach(pid);
    try {
      vm.loadAgent(source.toString(), actor + ";" + seconds + ";" + output);
    } finally {
      vm.detach();
    }
    System.out.println("Read-only visual observer attached; output=" + output);
  }

  public static void agentmain(String args, Instrumentation instrumentation) {
    try {
      String[] values = args.split(";", 3);
      long actorId = Long.parseLong(values[0]);
      int seconds = Integer.parseInt(values[1]);
      Path output = Path.of(values[2]);
      Files.createDirectories(output.toAbsolutePath().getParent());
      ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread thread = new Thread(r, "dragon-visual-readonly-observer");
        thread.setDaemon(true);
        return thread;
      });
      long stopAt = System.nanoTime() + TimeUnit.SECONDS.toNanos(seconds);
      executor.scheduleAtFixedRate(() -> {
        try {
          String sample = sampleOnEdt(actorId);
          Files.writeString(output, sample + "\n", StandardCharsets.UTF_8,
              StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND);
          if (System.nanoTime() >= stopAt) executor.shutdown();
        } catch (Throwable error) {
          try {
            Files.writeString(output, "{\"time\":\"" + Instant.now()
                + "\",\"observer_error\":\"" + escape(error.toString()) + "\"}\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE,
                StandardOpenOption.WRITE, StandardOpenOption.APPEND);
          } catch (IOException ignored) { }
        }
      }, 0, 500, TimeUnit.MILLISECONDS);
    } catch (Throwable error) {
      throw new IllegalStateException("could not start read-only observer", error);
    }
  }

  public static void premain(String args, Instrumentation instrumentation) {
    agentmain(args, instrumentation);
  }

  private static String sampleOnEdt(long actorId) throws Exception {
    final String[] result = new String[1];
    SwingUtilities.invokeAndWait(() -> {
      try {
        Object manager = call(Class.forName("bio"), "dpx");
        Object actor = call(manager, "jv", new Class<?>[] {long.class}, actorId);
        if (actor == null) {
          result[0] = "{\"time\":\"" + Instant.now() + "\",\"actor_id\":"
              + actorId + ",\"present\":false}";
          return;
        }
        Object graphic = call(actor, "dhw");
        Object callbackManager = call(graphic, "dha");
        Object appearanceStack = field(callbackManager, "hQY");
        Object heightStack = field(callbackManager, "hRp");
        Object scaleStack = field(callbackManager, "hRo");
        result[0] = "{\"time\":\"" + Instant.now() + "\",\"actor_id\":" + actorId
            + ",\"present\":true,\"class\":\"" + escape(actor.getClass().getName())
            + "\",\"appearance_model\":" + call(graphic, "bqo")
            + ",\"height_override\":" + call(graphic, "aLj")
            + ",\"height_base\":" + call(actor, "bcK")
            + ",\"static_animation\":\"" + escape(String.valueOf(call(graphic, "dhi")))
            + "\",\"visible\":" + call(graphic, "isVisible")
            + ",\"appearance_stack\":" + stack(appearanceStack)
            + ",\"height_stack\":" + stack(heightStack)
            + ",\"scale_stack\":" + stack(scaleStack) + "}";
      } catch (Throwable error) {
        result[0] = "{\"time\":\"" + Instant.now() + "\",\"actor_id\":"
            + actorId + ",\"sample_error\":\"" + escape(error.toString()) + "\"}";
      }
    });
    return result[0];
  }

  private static String stack(Object manager) throws Exception {
    if (manager == null) return "null";
    Object raw = field(manager, "hSA");
    if (!(raw instanceof Iterable<?> entries)) return "[]";
    List<String> rows = new ArrayList<>();
    for (Object entry : entries) {
      Object effect = field(entry, "hSC");
      long reference = ((Number) call(effect, "aZE")).longValue();
      String detail;
      try { detail = String.valueOf(field(entry, "hRS")); }
      catch (NoSuchFieldException absent) {
        try { detail = String.valueOf(field(entry, "hSH")); }
        catch (NoSuchFieldException alsoAbsent) { detail = String.valueOf(field(entry, "hTi")); }
      }
      rows.add("{\"effect_ref\":" + reference + ",\"value\":\"" + escape(detail) + "\"}");
    }
    return "[" + String.join(",", rows) + "]";
  }

  private static Object call(Object target, String name) throws Exception {
    return call(target, name, new Class<?>[0]);
  }

  private static Object call(Object target, String name, Class<?>[] parameterTypes, Object... args)
      throws Exception {
    Class<?> type = target instanceof Class<?> clazz ? clazz : target.getClass();
    Object receiver = target instanceof Class<?> ? null : target;
    Method method = type.getMethod(name, parameterTypes);
    return method.invoke(receiver, args);
  }

  private static Object field(Object target, String name) throws Exception {
    for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
      try {
        Field field = type.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(target);
      } catch (NoSuchFieldException ignored) { }
    }
    throw new NoSuchFieldException(target.getClass().getName() + "." + name);
  }

  private static String escape(String value) {
    return value.replace("\\", "\\\\").replace("\"", "\\\"")
        .replace("\n", "\\n").replace("\r", "\\r");
  }
}
