import java.lang.instrument.Instrumentation;import java.lang.reflect.*;import java.nio.file.*;import java.util.*;import javax.swing.SwingUtilities;
/** One-shot read-only diagnostics: never calls action.run or sends a packet. */
public class InspectMobInteractions{
 static Object call(Object o,String name)throws Exception{return o.getClass().getMethod(name).invoke(o);}
 static Object field(Object o,String name)throws Exception{Class<?>c=o.getClass();while(c!=null){try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(o);}catch(NoSuchFieldException e){c=c.getSuperclass();}}throw new NoSuchFieldException(name);}
 public static void agentmain(String output,Instrumentation instrumentation)throws Exception{
  List<String>rows=new ArrayList<>();SwingUtilities.invokeAndWait(()->{try{
   Object manager=Class.forName("bio").getMethod("dpx").invoke(null);Iterator<?>it=(Iterator<?>)call(manager,"bak");
   Class<?> action=Class.forName("cWi"),kind=Class.forName("fcz");Constructor<?>ctor=action.getDeclaredConstructor(kind);ctor.setAccessible(true);Object pve=kind.getField("rUX").get(null);
   while(it.hasNext()){Object actor=it.next();long id=((Number)call(actor,"Sn")).longValue();if(id>=0)continue;
    StringBuilder row=new StringBuilder("id="+id+" class="+actor.getClass().getName());
    Object graphics=call(actor,"dhw");for(String name:new String[]{"dsA","dnz","dpe","dpf","dsz","bqo"}){try{row.append(" "+name+"="+call(actor,name));}catch(Exception e){row.append(" "+name+"=ERR");}}
    row.append(" graphicsID="+call(graphics,"Sn"));
    Object candidate=ctor.newInstance(pve);action.getMethod("aK",Object.class).invoke(candidate,actor);
    row.append(" actionAllowed="+call(candidate,"bxQ")+" reasons="+field(candidate,"nFv"));
    BitSet reasons=(BitSet)field(candidate,"nFv");Object[]enums=Class.forName("cWk").getEnumConstants();for(int n=reasons.nextSetBit(0);n>=0;n=reasons.nextSetBit(n+1))row.append(" reason="+enums[n]);
    rows.add(row.toString());
   }
  }catch(Throwable e){rows.add("ERROR "+e);}});Files.write(Path.of(output),rows);
 }
 public static void main(String[]args)throws Exception{com.sun.tools.attach.VirtualMachine vm=com.sun.tools.attach.VirtualMachine.attach(args[0]);try{vm.loadAgent(args[1],args[2]);}finally{vm.detach();}}
}
