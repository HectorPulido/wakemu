import java.lang.reflect.*;
import java.util.*;

/** Original eYE selection, eYC sorting and direct child dispatch. No bdata load. */
public final class ProbeNativeGroup345 {
 static int checks;
 static void require(boolean ok,String label){if(!ok)throw new AssertionError(label);checks++;}
 static Object zero(Class<?> t){if(t==boolean.class)return false;if(t==int.class)return 0;if(t==short.class)return(short)0;if(t==byte.class)return(byte)0;if(t==long.class)return 0L;if(t==float.class)return 0f;if(t==double.class)return 0d;return null;}
 static void put(Object target,String name,Object value)throws Exception{
  for(Class<?> c=target.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(target,value);return;}catch(NoSuchFieldException ex){}
  throw new NoSuchFieldException(name);
 }
 static Object get(Object target,String name)throws Exception{
  for(Class<?> c=target.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(target);}catch(NoSuchFieldException ex){}
  throw new NoSuchFieldException(name);
 }
 static PV actor(int x,int y,short z){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
  switch(m.getName()){case "bcz":return x;case "bcA":return y;case "bcB":return z;case "baM":return new aBn(x,y,z);case "toString":return x+","+y;}
  return zero(m.getReturnType());
 });}
 static class Selected extends eWu {
  List<PV> rows; aBn center=new aBn(2,3,(short)1);
  Selected(eVn definition,PV caster,List<PV> rows){bfp=definition;bfr=caster;this.rows=rows;}
  public aBn bbd(){return center;}
  public List<PV> a(eVn def,amP caster,PN env,int x,int y,short z){
   require(x==2&&y==3&&z==1,"native selection coordinates");return rows;
  }
 }
 public static void main(String[] args)throws Exception{
  PV caster=actor(0,0,(short)0), first=actor(1,0,(short)2), second=actor(0,1,(short)-1);
  int[] criterionCalls={0};
  amb criterion=new amb(){public boolean bDm(){return false;}public Enum bDq(){return faf.rJB;}
   public int a(Object c,Object t,Object runner,Object env){criterionCalls[0]++;require(c==caster,"criterion caster");return t==first?0:1;}};
  eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->m.getName().equals("fKT")?criterion:zero(m.getReturnType()));
  Selected selection=new Selected(def,caster,List.of(first,second));
  require(eYE.e(selection,false).size()==2&&criterionCalls[0]==0,"unfiltered candidate list");
  List<PV> filtered=eYE.e(selection,true);
  require(filtered.size()==1&&filtered.get(0)==first&&criterionCalls[0]==2,"criterion filters every candidate");
  require(faf.Te(99)==faf.rJB,"unknown sort is NONE");
  List<int[]> points=Arrays.asList(new int[]{0,-1},new int[]{-1,0},new int[]{0,1},new int[]{1,0},new int[]{0,0},new int[]{2,0});
  List<int[]> sorted=new ArrayList<>(points);sorted.sort(faf.Te(1).au(new aBn(0,0)));
  int[][] expected={{0,0},{1,0},{0,1},{-1,0},{0,-1},{2,0}};
  for(int i=0;i<expected.length;i++)require(Arrays.equals(expected[i],sorted.get(i)),"Manhattan then angle "+i);
  sorted=new ArrayList<>(points);sorted.sort(faf.Te(2).au(new aBn(0,0)));
  for(int i=0;i<expected.length;i++)require(Arrays.equals(expected[expected.length-1-i],sorted.get(i)),"reverse spiral "+i);
  eYC group=new eYC();put(group,"bfr",caster);put(group,"ePP",1);
  Method sort=eYC.class.getDeclaredMethod("aU",List.class);sort.setAccessible(true);
  List<PV> actors=new ArrayList<>(List.of(second,first));sort.invoke(group,actors);
  require(actors.get(0)==first,"eYC applies original comparator to PV x/y");
  List<Object[]> deliveries=new ArrayList<>();
  eVn child=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
   if(m.getName().equals("a")&&a!=null&&a.length==10){deliveries.add(a.clone());return null;}return zero(m.getReturnType());
  });
  Method dispatch=eYC.class.getDeclaredMethod("a",Iterator.class,PS.class,PV.class);dispatch.setAccessible(true);
  eVt context=eVt.a(false,false,null);
  dispatch.invoke(group,List.of(child,child).iterator(),context,second);
  require(deliveries.size()==2,"each selected actor gets whole child list");
  for(Object[] a:deliveries){require(a[1]==caster&&a[4].equals(0)&&a[5].equals(1)&&a[6].equals((short)-1)&&a[7]==second&&a[8]==context&&a[9].equals(false),"direct PV and actual XYZ");}
  context.bal();
  put(group,"rGu",3);put(group,"rGv",true);put(group,"rGw",false);put(group,"ePP",2);
  eYg clone=group.fPD();
  require(get(clone,"rGu").equals(3)&&get(clone,"rGv").equals(true)&&get(clone,"rGw").equals(false)&&get(clone,"ePP").equals(0),"clone preserves count/filter/shuffle; C reseeds sort");
  group.aWr();require(get(group,"rGu").equals(-1)&&get(group,"rGv").equals(false)&&get(group,"rGw").equals(true)&&get(group,"ePP").equals(0),"reset defaults");
  System.out.println("PASS "+checks+" original eYC/eYE/faf checks; no game catalog loaded");
 }
}
