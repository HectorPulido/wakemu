import java.util.*;
/** Original eOs/eJW against a real Qs collection and real point-shaped Qq. */
public class ProbeNativeAreaPredicates {
 static class Actor extends ProbeNativeFightersBreedRange.A {public aAS bcy(){return aAS.wL(3);}}
 static Actor actor(int x)throws Exception{Actor a=(Actor)ProbeNativeFightersBreedRange.U.allocateInstance(Actor.class);a.x=x;return a;}
 static class Manager extends Qs {Collection<Qq> rows;public Collection<Qq> bdm(){return rows;}public Qq dp(long id){return null;}}
 static class Fight extends ProbeNativeFightersBreedRange.F {Manager manager;public Qs baf(){return manager;}}
 static class Hour extends faZ {
  int type;Hour(Qr q){super(q);}Hour(){super();}
  protected Qq bcs(){return new Hour();}public List<amP> d(amP p){return n(p);}
  public anS bEs(){return bcD().bEs();}public int aeV(){return type;}
 }
 static Hour area(long uid,int x,int y,int type,PV owner){
  Hour template=new Hour(new Qr().oK(1546).b(anD.bEz()).oN(1));
  Hour result=(Hour)template.b(new fbm(uid,x,y,(short)9,null,7,owner,(short)1,aAS.wL(3)));result.type=type;result.bcT();return result;
 }
 static long count(Fight f,Object caster,Object target,String selector,int type,int min,int max,boolean owned){
  return new eJW(new ArrayList<alS>(List.of(new amc(selector),new alw(type),new alw(min),new alw(max),new alu(owned)))).d(caster,target,null,f);
 }
 static void check(long actual,long expected,String name){if(actual!=expected)throw new AssertionError(name+":"+actual+"!="+expected);System.out.println("PASS "+name+"="+actual);}
 public static void main(String[]args)throws Exception{
  Actor caster=actor(0),target=actor(2);
  Fight f=(Fight)ProbeNativeFightersBreedRange.U.allocateInstance(Fight.class);Manager m=new Manager();f.manager=m;
  m.rows=List.of(area(901,0,0,1,caster),area(902,2,0,1,target),area(903,4,0,2,caster));
  check(count(f,caster,target,"caster",1,0,2,false),2,"typeAndInclusiveRange");
  check(count(f,caster,target,"caster",1,0,2,true),1,"casterOwnership");
  check(count(f,caster,new aBn(2,0,(short)99),"TaRgEt",1,0,0,false),1,"targetCellCaseInsensitiveIgnoresZ");
  check(count(f,caster,target,"caster",1,99,-1,false),2,"negativeMaxBypassesMinimum");
  check(count(f,caster,target,"wrong",1,0,2,false),2,"otherSelectorMeansCaster");
  check(count(f,null,target,"caster",1,0,2,false),0,"missingCenter");
  check(new eOs("caster",1,true).a(caster,target,null,f),0,"ownAreaOnCaster");
  check(new eOs("target",1,true).a(caster,target,null,f),0,"ownedUsesSelectedTarget");
  check(new eOs("target",2,false).a(caster,target,null,f),-1,"differentType");
  check(new eOs("target",999,false).a(caster,target,null,f),-1,"invalidEnum");
  check(new eOs("target",1,false).a(caster,new aBn(0,0,(short)0),null,f),-1,"onAreaRequiresFighterNotCell");
  System.out.println("Valid native fbp IDs="+Arrays.toString(Arrays.stream(fbp.values()).mapToInt(fbp::aIc).toArray()));
 }
}
