import java.lang.reflect.*;
/** Original runner fOs capability; no catalog or connection. */
public class ProbeNativeCollisionCapability {
 public static void main(String[] args) throws Exception {
  for(Class<?> type:new Class<?>[]{eXK.class,eXJ.class,eXp.class,eXq.class}){
   Object runner=type.getDeclaredConstructor().newInstance();
   Method method=type.getDeclaredMethod("fOs");method.setAccessible(true);
   boolean actual=(boolean)method.invoke(runner);
   boolean expected=type==eXK.class||type==eXJ.class;
   if(actual!=expected)throw new AssertionError(type.getName());
   System.out.println(type.getName()+".fOs="+actual);
  }
 }
}
