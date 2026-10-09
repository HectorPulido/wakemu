import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import javax.swing.SwingUtilities;

/** One-shot read-only snapshot of native object payloads and the current scene object registry. */
public final class InteractiveRegistryDiagnosticAgent {
  private static String esc(Object v) {
    String s = String.valueOf(v); StringBuilder b = new StringBuilder("\"");
    for (int i=0;i<s.length();i++) { char c=s.charAt(i); switch(c) {
      case '"': b.append("\\\""); break; case '\\': b.append("\\\\"); break;
      case '\n': b.append("\\n"); break; case '\r': b.append("\\r"); break; case '\t': b.append("\\t"); break;
      default: if(c<32)b.append(String.format("\\u%04x",(int)c)); else b.append(c);
    }} return b.append('"').toString();
  }
  private static Object field(Object o, String n) throws Exception {
    for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass()) try { Field f=c.getDeclaredField(n); f.setAccessible(true); return f.get(o); } catch(NoSuchFieldException ignored){}
    throw new NoSuchFieldException(n);
  }
  private static Object type(short id) { try { return Class.forName("bEE").getMethod("cb",short.class).invoke(null,id); } catch(Throwable e) { return null; } }
  private static String typeName(short id) {
    Object t=type(id); if(t==null)return "unknown";
    try { return String.valueOf(t.getClass().getMethod("aYh").invoke(t)); } catch(Throwable ignored) { return String.valueOf(t); }
  }
  private static int[] chunkFor(Object scene, int x, int y) {
    try { for(Object p:(Iterable<?>)scene.getClass().getMethod("ble").invoke(scene)) {
      if((Boolean)p.getClass().getMethod("aF",int.class,int.class).invoke(p,x,y))
        return new int[]{((Number)p.getClass().getMethod("getX").invoke(p)).intValue(),((Number)p.getClass().getMethod("getY").invoke(p)).intValue(),((Number)p.getClass().getMethod("getWidth").invoke(p)).intValue(),((Number)p.getClass().getMethod("getHeight").invoke(p)).intValue()};
    }} catch(Throwable ignored){} return null;
  }
  private static String info(bEG o, Object scene) {
    StringBuilder b=new StringBuilder("{");
    try {
      long id=o.Sn(); float x=o.getWorldX(), y=o.getWorldY(), z=o.getAltitude(); short kind=o.bem();
      b.append("\"id\":").append(id).append(",\"class\":").append(esc(o.getClass().getName()))
       .append(",\"nativeTypeId\":").append(kind).append(",\"nativeType\":").append(esc(typeName(kind)))
       .append(",\"name\":").append(esc(o.getName())).append(",\"x\":").append(x).append(",\"y\":").append(y).append(",\"z\":").append(z)
       .append(",\"visible\":").append(o.isVisible()).append(",\"usable\":").append(o.isUsable()).append(",\"selectable\":").append(o.isSelectable())
       .append(",\"stateShort\":").append(o.dVL()).append(",\"stateInt\":").append(o.dVM()).append(",\"state\":").append(esc(o.dVN()))
       .append(",\"actionCount\":").append(o.bee().length).append(",\"flag\":").append(o.bqo());
      int[] c=chunkFor(scene,(int)Math.floor(x),(int)Math.floor(y));
      b.append(",\"sceneChunk\":"); if(c==null)b.append("null"); else b.append("{\"x\":").append(c[0]).append(",\"y\":").append(c[1]).append(",\"width\":").append(c[2]).append(",\"height\":").append(c[3]).append('}');
    } catch(Throwable e) { b.append("\"inspectError\":").append(esc(e.toString())); }
    return b.append('}').toString();
  }
  public static void agentmain(String output, Instrumentation inst) throws Exception {
    String[] ids=System.getProperty("wakfu.diag.objectIds","26842,26865,26878").split(",");
    List<Long> wanted=new ArrayList<>(); for(String s:ids)wanted.add(Long.parseLong(s.trim()));
    StringBuilder[] result={new StringBuilder()};
    SwingUtilities.invokeAndWait(()->{try {
      Object raw=Class.forName("bEC").getMethod("dVG").invoke(null);
      Object scene=Class.forName("cdE").getMethod("exN").invoke(null);
      Collection<?> loaded=(Collection<?>)scene.getClass().getMethod("exP").invoke(scene);
      Map<Long,Object> rendered=new HashMap<>(); int renderedCount=0;
      for(Object o:loaded) if(o instanceof bEG){renderedCount++;rendered.put(((bEG)o).Sn(),o);}
      Object mapScreen=Class.forName("cdG").getMethod("exW").invoke(null);
      Object mapMeta=mapScreen.getClass().getMethod("exX").invoke(mapScreen);
      int mapId=mapMeta==null?-1:((Number)mapMeta.getClass().getField("cgb").get(mapMeta)).intValue();
      long worldMapId=-1; try {worldMapId=((Number)field(mapScreen,"bqh")).longValue();}catch(Throwable ignored){}
      StringBuilder j=new StringBuilder("{\"capturedAt\":").append(esc(Instant.now())).append(",\"mapId\":").append(mapId).append(",\"worldMapId\":").append(worldMapId).append(",\"sceneObjectCount\":").append(loaded.size()).append(",\"sceneInteractiveCount\":").append(renderedCount).append(",\"objects\":[");
      for(int i=0;i<wanted.size();i++){
        long id=wanted.get(i); if(i>0)j.append(','); Object msg=raw.getClass().getMethod("ds",long.class).invoke(raw,id); Object o=rendered.get(id);
        j.append("{\"id\":").append(id).append(",\"rawPresent\":").append(msg!=null);
        if(msg!=null){short t=msg.getClass().getField("bkI").getShort(msg); byte[] payload=(byte[])msg.getClass().getField("bkJ").get(msg);
          j.append(",\"rawTypeId\":").append(t).append(",\"rawType\":").append(esc(typeName(t))).append(",\"rawPayloadBytes\":").append(payload.length);
        }
        j.append(",\"renderedPresent\":").append(o!=null);
        if(o!=null)j.append(",\"rendered\":").append(info((bEG)o,scene));
        j.append('}');
      }
      j.append("]}"); result[0]=j;
    } catch(Throwable e) { result[0]=new StringBuilder("{\"capturedAt\":").append(esc(Instant.now())).append(",\"error\":").append(esc(e.toString())).append('}'); }});
    Path p=Path.of(output); Files.createDirectories(p.getParent()); Files.writeString(p,result[0].toString()+"\n",StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
  }
}
