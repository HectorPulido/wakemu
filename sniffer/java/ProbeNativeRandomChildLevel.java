import java.lang.reflect.*;
/** Original eYx calculation, eVt.SP and max-exclusive GS.p contract. */
public class ProbeNativeRandomChildLevel {
 static class Runner extends eYx {
  void definition(int lo,int hi){bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->{
   if(m.getName().equals("a")&&a.length==3)return (int)a[0]==0?lo:hi;
   throw new UnsupportedOperationException(m.getName());});}
  int draw(){C(null);return getValue();}
  eVt child(){return j(null);}
 }
 public static void main(String[]args)throws Exception{
  for(int[]bounds:new int[][]{{0,1},{-7,-6},{42,42},{1,4}}){
   Runner r=new Runner();r.definition(bounds[0],bounds[1]);
   for(int n=0;n<40;n++){
    int v=r.draw();if(v<bounds[0]||v>bounds[1]||(bounds[0]!=bounds[1]&&v==bounds[1]))throw new AssertionError();
    eVt context=r.child();if(context.Oh()!=v||context.fLN()||context.fLO())throw new AssertionError();context.bal();
   }
  }
  Runner codec=new Runner();codec.definition(42,42);codec.draw();eVt context=codec.child();
  if(args.length>0)java.nio.file.Files.write(java.nio.file.Path.of(args[0]),context.fLV().toByteArray());context.bal();
  Runner invalid=new Runner();invalid.definition(4,1);try{invalid.draw();throw new AssertionError();}catch(IllegalArgumentException expected){}
  System.out.println("Native eYx: four bounds/SP contracts x40 plus inverted range rejection: 161 PASS");
 }
}
