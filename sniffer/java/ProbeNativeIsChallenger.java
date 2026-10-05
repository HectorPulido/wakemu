import java.lang.reflect.Proxy;import java.util.ArrayList;
/** Native eNC checks player/companion kinds, independent of fight teams. */
public class ProbeNativeIsChallenger {
 static eHg actor(eHh kind){return(eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},(p,m,a)->{if(m.getName().equals("a")&&a[0] instanceof eHh)return kind.a((eHh)a[0]);throw new UnsupportedOperationException(m.getName());});}
 static eNC criterion(String selector){ArrayList<alS> args=new ArrayList<>();if(selector!=null)args.add(new amc(selector));return new eNC(args);}
 public static void main(String[] args){Object pc=actor(eHh.pNj),npc=actor(eHh.pNk),companion=actor(eHh.pNl);
  if(criterion(null).a(pc,npc,null,null)!=-1 ||criterion("CASTER").a(pc,npc,null,null)!=0)throw new AssertionError("targetdefault");
  if(criterion(null).a(npc,companion,null,null)!=0 ||criterion(null).a(npc,null,null,null)!=-1)throw new AssertionError("companion/null");
  System.out.println("eNC defaulttarget NPCfalse; caster PCtrue; companiontrue; missingtargetfalse");
 }
}
