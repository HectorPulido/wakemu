import java.lang.reflect.Proxy;import java.util.ArrayList;
public class ProbeNativeIsPlayer {
 static eHg actor(eHh kind){return(eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},(p,m,a)->{if(m.getName().equals("a")&&a[0] instanceof eHh)return kind.a((eHh)a[0]);throw new UnsupportedOperationException(m.getName());});}
 static eOI criterion(String selector){ArrayList<alS> args=new ArrayList<>();if(selector!=null)args.add(new amc(selector));return new eOI(args);}
 public static void main(String[] args){Object pc=actor(eHh.pNj),npc=actor(eHh.pNk),companion=actor(eHh.pNl);
 if(criterion(null).a(pc,npc,null,null)!=-1||criterion("CASTER").a(pc,npc,null,null)!=0||criterion(null).a(npc,pc,null,null)!=0||criterion(null).a(npc,companion,null,null)!=-1||criterion(null).a(pc,null,null,null)!=-1||criterion("unknown").a(pc,pc,null,null)!=-1)throw new AssertionError();
 System.out.println("IsPlayer original 6 cases PASS");}}
