import java.util.*;
public class ProbeNativeActionPresence {
 static class Manager extends eZV {List<Qe> effects=new ArrayList<>();Manager(){super(null);}public Iterator<Qe> iterator(){return effects.iterator();}}
 static class Actor extends ProbeNativeLevelGroup.Actor {Manager manager=new Manager();public eZV drJ(){return manager;}}
 static eMi predicate(String selector,int action){ArrayList<alS>a=new ArrayList<>();a.add(new amc(selector));a.add(new alw(action));return new eMi(a);}
 public static void main(String[]args){Actor caster=new Actor(),target=new Actor();eXE effect=new eXE();effect.lV(20);target.manager.effects.add(effect);
  if(predicate("target",20).a(caster,target,null,null)!=0||predicate("caster",20).a(caster,target,null,null)!=-1||predicate("target",197707).a(caster,target,null,null)!=-1)throw new AssertionError("manager/action binding");
  target.manager.effects.clear();if(predicate("target",20).a(caster,target,null,null)!=-1||predicate("target",20).a(caster,null,null,null)!=-1)throw new AssertionError("remove/null");
  System.out.println("PASS eMi/eGj.PK/PM real manager action20 presence,target/caster distinction,removal,null");
 }
}
