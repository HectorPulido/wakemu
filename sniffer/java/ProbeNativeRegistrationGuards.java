import java.util.*;import java.lang.reflect.*;
/** Exact installed registry classes and guard method owners; not a gameplay execution. */
public final class ProbeNativeRegistrationGuards {
 public static void main(String[] args)throws Exception {
  Set<Integer> selected=Set.of(20,31,41,191,56,57,192,193,986,1013,1201,1202,330,341,352,1103,400,402,877,649,1065);
  for(Field f:eVi.class.getDeclaredFields()){
   if(f.getType()!=eVj.class||!Modifier.isStatic(f.getModifiers()))continue;
   f.setAccessible(true);eVj registry=(eVj)f.get(null);if(!selected.contains(registry.d()))continue;
   Qe runner=(Qe)registry.bkv();Class<?> cls=runner.getClass();
   System.out.println("effect="+registry.d()+" runner="+cls.getName()+" aZNowner="+cls.getMethod("aZN").getDeclaringClass().getName()+" Tyowner="+cls.getMethod("Ty").getDeclaringClass().getName()+" bbWowner="+cls.getMethod("bbW").getDeclaringClass().getName());
  }
 }
}
