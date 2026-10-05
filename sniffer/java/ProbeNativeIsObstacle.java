import java.util.*;
public class ProbeNativeIsObstacle {
 static class Actor extends ProbeNativeFightersBreedRange.A {
  boolean active=true,ally;Set<PE> props=new HashSet<>();
  public boolean dnz(){return active;}public boolean dnS(){return ally;}
  public boolean a(PE p){return props.contains(p);}
 }
 static class Map extends QI {java.util.Map<String,QK> cells=new HashMap<>();public QK V(int x,int y){return cells.get(x+","+y);}}
 static class Fight extends ProbeNativeFightersBreedRange.F {Map map=new Map();public QI bad(){return map;}}
 static Actor actor(int x,int y,int r)throws Exception{Actor a=(Actor)ProbeNativeFightersBreedRange.U.allocateInstance(Actor.class);a.active=true;a.props=new HashSet<>();a.x=x;a.y=y;a.radius=(byte)r;return a;}
 static int query(Fight f,Object caster,Object target,String selector){var args=new ArrayList<alS>();if(selector!=null)args.add(new amc(selector));return new eOp(args).a(caster,target,null,f);}
 static void check(boolean b,String s){if(!b)throw new AssertionError(s);System.out.println("PASS "+s);}
 public static void main(String[]args)throws Exception{
  Actor caster=actor(0,0,0),target=actor(3,3,0);Fight f=(Fight)ProbeNativeFightersBreedRange.U.allocateInstance(Fight.class);f.map=new Map();
  check(query(f,caster,target,null)==-1,"empty QI is false");f.map.cells.put("0,0",caster);
  check(query(f,caster,target,null)==0,"registered own object blocks");
  caster.active=false;check(query(f,caster,target,null)==-1,"dnz false");caster.active=true;
  check(query(f,caster,new aBn(0,0,(short)0),"target")==-1,"cell is not fighter");
  caster.radius=1;f.map.cells.clear();f.map.cells.put("1,1",target);check(query(f,caster,target,null)==-1,"positive radius upper exclusive");
  f.map.cells.put("-1,-1",target);check(query(f,caster,target,null)==0,"positive radius lower inclusive");
  for(boolean ally:new boolean[]{false,true})for(boolean invisible:new boolean[]{false,true})for(boolean revealed:new boolean[]{false,true})for(boolean superior:new boolean[]{false,true})for(boolean noLos:new boolean[]{false,true}){
   caster.ally=ally;caster.props.clear();if(invisible)caster.props.add(ffe.sdC);if(revealed)caster.props.add(ffe.sdD);if(superior)caster.props.add(ffe.sdO);if(noLos)caster.props.add(ffe.sex);
   boolean expectedP=ally||((revealed||!invisible)&&!superior),expectedQ=!superior&&(revealed||!invisible)&&!noLos;
   if(caster.bcP()!=expectedP||caster.bcQ()!=expectedQ)throw new AssertionError("viewer blocking flags");
  }
  System.out.println("PASS native big/eGj viewer blocking flags32 combinations");
 }
}
