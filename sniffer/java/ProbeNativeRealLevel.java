import java.lang.reflect.*;import java.util.ArrayList;
/** Offline native eLc criterion with an explicitly modulated own player. */
public class ProbeNativeRealLevel {
 static biB actor(short level)throws Exception {
  biB actor=new biB(false);
  Object progression=Proxy.newProxyInstance(fCo.class.getClassLoader(),new Class<?>[]{fCo.class},(p,m,a)->{if(m.getName().equals("cmZ"))return level;throw new UnsupportedOperationException(m.getName());});
  Field field=biB.class.getDeclaredField("iiz");field.setAccessible(true);field.set(actor,progression);
  Field build=biB.class.getDeclaredField("iax");build.setAccessible(true);((eQW)build.get(actor)).a(0,new eQT("offline",20,0,1,true));
  return actor;
 }
 static eLc criterion(String selector){ArrayList<alS> args=new ArrayList<>();if(selector!=null)args.add(new amc(selector));return new eLc(args);}
 public static void main(String[] args)throws Exception {
  biB caster=actor((short)200),target=actor((short)60);
  if(caster.cmZ()!=20 || caster.drm()!=200)throw new AssertionError("native progression distinct");
  if(criterion(null).d(caster,target,null,null)!=200 ||criterion("TARGET").d(caster,target,null,null)!=60)throw new AssertionError("native selector");
  if(criterion("EVENTTARGET").d(caster,target,null,null)!=200 ||criterion("eventTarget").d(caster,target,null,null)!=-1)throw new AssertionError("native exact event selector");
  System.out.println("eLc real200 vs effective20; target60; exact eventTarget requires event context");System.exit(0);
 }
}
