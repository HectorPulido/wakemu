import java.awt.*;
import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.util.*;
import javax.swing.SwingUtilities;
import com.google.gson.Gson;
import com.jogamp.opengl.*;

public class UiSnapshotAgent {
    public static void agentmain(String directory, Instrumentation inst) throws Exception {
        String[] arguments = directory.split("\\|");
        Path root = Path.of(arguments[0]);
        java.util.List<Map<String, Object>> info = new ArrayList<>();
        SwingUtilities.invokeAndWait(() -> {
            for (Frame f : Frame.getFrames()) {
                if (f.isShowing()) {
                    if (arguments.length == 4 && arguments[1].equals("resize")) {
                        f.setSize(Integer.parseInt(arguments[2]), Integer.parseInt(arguments[3]));
                        f.validate();
                    }
                    collect(f, info);
                    if (arguments.length == 4 && arguments[1].equals("click")) {
                        click(f, Integer.parseInt(arguments[2]), Integer.parseInt(arguments[3]));
                    }
                }
            }
        });
        Files.writeString(root.resolve("ui-info.json"), new Gson().toJson(info));
        Class<?> singleton = Class.forName("aGZ");
        Object app = singleton.getMethod("cfK").invoke(null);
        Object renderer = app.getClass().getMethod("bmE").invoke(app);
        Class<?> shotClass = Class.forName("aSH");
        Object shot = shotClass.getConstructor().newInstance();
        shotClass.getField("dQe").set(shot, root.resolve("builtin-screen.png").toFile());
        renderer.getClass().getMethod("a", Class.forName("awW")).invoke(renderer, shot);
    }
    private static boolean click(Component component, int x, int y) {
        if (component instanceof GLAutoDrawable) {
            long now = System.currentTimeMillis();
            component.requestFocusInWindow();
            component.dispatchEvent(new java.awt.event.MouseEvent(component, java.awt.event.MouseEvent.MOUSE_MOVED, now,
                0, x, y, 0, false, java.awt.event.MouseEvent.NOBUTTON));
            component.dispatchEvent(new java.awt.event.MouseEvent(component, java.awt.event.MouseEvent.MOUSE_PRESSED, now,
                java.awt.event.InputEvent.BUTTON1_DOWN_MASK, x, y, 1, false, java.awt.event.MouseEvent.BUTTON1));
            component.dispatchEvent(new java.awt.event.MouseEvent(component, java.awt.event.MouseEvent.MOUSE_RELEASED, now + 30,
                0, x, y, 1, false, java.awt.event.MouseEvent.BUTTON1));
            component.dispatchEvent(new java.awt.event.MouseEvent(component, java.awt.event.MouseEvent.MOUSE_CLICKED, now + 31,
                0, x, y, 1, false, java.awt.event.MouseEvent.BUTTON1));
            return true;
        }
        if (component instanceof Container parent) for(Component child:parent.getComponents()) if(click(child,x,y)) return true;
        return false;
    }
    private static void collect(Component c, java.util.List<Map<String, Object>> info) {
        Map<String,Object> entry = new LinkedHashMap<>();
        entry.put("class", c.getClass().getName());
        entry.put("size", c.getWidth()+"x"+c.getHeight());
        entry.put("location", c.isShowing() ? c.getLocationOnScreen().toString() : "hidden");
        if (c instanceof GLAutoDrawable drawable) {
            entry.put("surface", drawable.getSurfaceWidth()+"x"+drawable.getSurfaceHeight());
            drawable.invoke(false, gl -> {
                int[] viewport = new int[4]; gl.getGL().glGetIntegerv(GL2.GL_VIEWPORT,viewport,0);
                entry.put("viewport", viewport);
                return true;
            });
        }
        info.add(entry);
        if (c instanceof Container parent) for(Component child:parent.getComponents()) collect(child,info);
    }
}
