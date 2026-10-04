import java.lang.reflect.*;
public class ProbeNativeEventTargets {
 static PV actor(long id){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{if(m.getName().equals("Sn"))return id;throw new UnsupportedOperationException(m.getName());});}
 static final class Manager extends Qf { public PV bch(){return actor(83);}public Qi bci(){return null;}}
 static final class Group extends eYg {
  Group(long caster,long target){this.bfr=actor(caster);this.bfs=actor(target);}
  public Qf bbp(){return new Manager();}
  void definition(Qd target,Qb caster){this.bfp=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(p,m,a)->switch(m.getName()){
   case "aZV"->target;case "aZW"->caster;case "aZE"->1;default->throw new UnsupportedOperationException(m.getName());});}
  Long target(Qe source){PV p=l(source);return p==null?null:p.Sn();}
  Long caster(Qe source){PV p=m(source);return p==null?null:p.Sn();}
 }
 public static void main(String[]args){
  Group source=new Group(71,72),listener=new Group(81,82);
  for(Qd target:Qd.values()){listener.definition(target,null);System.out.println("target "+target.name()+" code="+target.aKg()+" id="+listener.target(source));}
  for(Qb caster:Qb.values()){listener.definition(Qd.bfe,caster);System.out.println("caster "+caster.name()+" code="+caster.aKg()+" id="+listener.caster(source));}
 }
}
