import java.lang.reflect.*;
import java.util.*;

/** Original eYk private population and sort, against explicit offline QI facts. */
public final class ProbeNativeCellGroup349 {
 static int checks;
 static void require(boolean ok,String message){if(!ok)throw new AssertionError(message);checks++;}
 static class Grid extends QI {
  Grid(){bpZ=-1;bqa=-1;bqd=3;bqe=3;biD=new short[9];Arrays.fill(biD,(short)256);biD[0]=(short)128;}
  public short X(int x,int y){return x==1&&y==1?Short.MIN_VALUE:(short)4;}
 }
 @SuppressWarnings("unchecked")
 public static void main(String[]args)throws Exception{
  Grid grid=new Grid();eYk runner=new eYk();
  PV caster=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
   if(m.getName().equals("baM"))return new aBn(0,0,(short)4);
   if(m.getName().equals("bcy"))return aAS.wL(3);
   return ProbeNativeGroup345.zero(m.getReturnType());
  });
  PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},
   (p,m,a)->m.getName().equals("bad")?grid:ProbeNativeGroup345.zero(m.getReturnType()));
  anc[] area={anA.bEy()};
  eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},
   (p,m,a)->m.getName().equals("aZP")?area[0]:ProbeNativeGroup345.zero(m.getReturnType()));
  ProbeNativeGroup345.put(runner,"bfp",definition);ProbeNativeGroup345.put(runner,"bfr",caster);
  ProbeNativeGroup345.put(runner,"bfw",context);ProbeNativeGroup345.put(runner,"bft",new aBn(0,0,(short)4));
  Method population=eYk.class.getDeclaredMethod("fPX");population.setAccessible(true);
  List<int[]> rows=(List<int[]>)population.invoke(runner);
  require(rows.size()==8,"whole map excludes bit128 only");
  require(rows.get(7)[0]==1&&rows.get(7)[1]==1,"whole map preserves row order and absent height");
  ProbeNativeGroup345.put(runner,"rFv",true);
  require(((List<?>)population.invoke(runner)).size()==8,"null criterion bypasses filtered whole-map height removal");
  anG rectangle=new anG();rectangle.p(new int[]{3,3});area[0]=rectangle;
  ProbeNativeGroup345.put(runner,"rFv",false);
  rows=(List<int[]>)population.invoke(runner);
  require(rows.stream().noneMatch(v->v[0]==1&&v[1]==1),"ordinary area removes missing selected height");
  Method sort=eYk.class.getDeclaredMethod("aT",List.class);sort.setAccessible(true);
  int[][] expected={{0,0},{1,0},{0,1},{-1,0},{0,-1},{2,0}};
  for(int mode:new int[]{1,2,99}){
   ProbeNativeGroup345.put(runner,"ePP",mode);
   List<int[]> cells=new ArrayList<>(List.of(new int[]{0,-1},new int[]{-1,0},new int[]{0,1},new int[]{1,0},new int[]{0,0},new int[]{2,0}));
   int[][] original=cells.toArray(int[][]::new);sort.invoke(runner,cells);
   for(int i=0;i<cells.size();i++)require(Arrays.equals(cells.get(i),mode==99?original[i]:expected[mode==1?i:5-i]),"original eYk sort "+mode+"/"+i);
  }
  System.out.println("PASS "+checks+" original eYk population/sort checks; no game catalogs loaded");
 }
}
