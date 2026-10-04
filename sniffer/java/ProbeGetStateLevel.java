import java.lang.reflect.Proxy;import java.util.ArrayList;
public class ProbeGetStateLevel{
 static eHg actor(int level){return(eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},(p,m,a)->switch(m.getName()){case "a"->true;case "df"->((long)a[0])==3617?level:-1;default->throw new UnsupportedOperationException(m.getName());});}
 static eLs criterion(boolean target,int reference){ArrayList<alS> p=new ArrayList<>();p.add(new alw(reference));if(target)p.add(new amc("target"));return new eLs(p);}
 public static void main(String[]a){Object caster=actor(124),target=actor(50);if(criterion(false,3617).d(caster,target,null,null)!=124)throw new AssertionError();if(criterion(true,3617).d(caster,target,null,null)!=50)throw new AssertionError();if(criterion(false,999).d(caster,target,null,null)!=-1)throw new AssertionError();System.out.println("NativeeLs defaultcaster124,target50,absentstate-1");}}
