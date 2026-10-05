import java.lang.reflect.*;
import java.util.ArrayList;
/** Calls the actual eJE predicate with current runner in argument3. */
public class ProbeNativeContainerLevel {
 static Field field(String name)throws Exception{Field f=Qe.class.getDeclaredField(name);f.setAccessible(true);return f;}
 public static void main(String[]args)throws Exception{
  eJE query=new eJE(new ArrayList<alS>());eYg current=new eYg();
  if(query.d(null,null,null,null)!=0)throw new AssertionError("null current");
  field("bfq").set(current,Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class[]{eVo.class},(p,m,a)->{
   if(m.getName().equals("cmZ"))return(short)200;throw new UnsupportedOperationException(m.getName());}));
  if(query.d(null,null,current,null)!=200)throw new AssertionError("actual PL");
  eVt context=new eVt();context.SP(65538);field("bfu").set(current,context);
  if(query.d(null,null,current,new Object())!=2)throw new AssertionError("current short override");
  context.SP(-1);if(query.d(null,null,current,null)!=200)throw new AssertionError("sentinel");
  field("bfq").set(current,null);if(query.d(null,null,current,null)!=0)throw new AssertionError("null PL");
  try{query.d(null,null,new Object(),null);throw new AssertionError("wrong current type");}catch(ClassCastException expected){}
  System.out.println("PASS actual eJE current runner/null/PL/override/sentinel/type six cases");
 }
}
