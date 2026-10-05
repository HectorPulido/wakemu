import java.lang.reflect.*;
/** Original aES diagnostic when the same action is restarted before completion. */
public final class ProbeNativeCrossScriptCompletion {
 public static void main(String[]args)throws Exception {
  aES action=new aES(228,3,3);
  Field running=aES.class.getDeclaredField("dIO");running.setAccessible(true);running.setInt(action,2);
  Field pending=aES.class.getDeclaredField("dIP");pending.setAccessible(true);pending.setBoolean(action,true);
  // Callback contract needs no Lua execution; allocate the native instance
  // without opening the unavailable Lua JNI, then initialize its identity/list.
  Field singleton=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");singleton.setAccessible(true);
  sun.misc.Unsafe unsafe=(sun.misc.Unsafe)singleton.get(null);
  aEp wrong=(aEp)unsafe.allocateInstance(aEp.class);
  Field identity=aEp.class.getDeclaredField("dHm");identity.setAccessible(true);identity.setInt(wrong,4);
  Field observers=aEp.class.getDeclaredField("dHv");observers.setAccessible(true);observers.set(wrong,new java.util.ArrayList<>());
  java.io.StringWriter diagnostic=new java.io.StringWriter();
  org.apache.log4j.WriterAppender appender=new org.apache.log4j.WriterAppender(new org.apache.log4j.PatternLayout("%m%n"),diagnostic);
  org.apache.log4j.Logger.getRootLogger().addAppender(appender);
  action.a(wrong);
  if(!diagnostic.toString().contains("script(2)")||!diagnostic.toString().contains("script(4)"))throw new AssertionError("Expected original cross-script diagnostic");
  System.out.print(diagnostic.toString());
  if(running.getInt(action)!=-1||pending.getBoolean(action))throw new AssertionError("Cross completion does not close waiting action");
  System.out.println("PASS original aES expected script2 receives script4: logs diagnostic and STILL completes action");
 }
}
