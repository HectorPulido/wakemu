import java.nio.file.*;import java.lang.reflect.*;import java.util.*;
public class ProbeHPLevelGroup {
 static Field field(Object o,String n)throws Exception{for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 static class Stat extends PA {int cur,max;Stat(int c,int m){cur=c;max=m;}public int aYS(){return cur;}public int aYT(){return cur;}public int aYU(){return max;}public int aYV(){return 0;}public int aYW(){return 0;}public int om(int x){return 0;}public int aYX(){return 0;}public void on(int x){}public int nG(int x){return 0;}public int oo(int x){return 0;}public int op(int x){return 0;}public int oq(int x){return 0;}public void or(int x){}public void os(int x){}public void aYY(){}public PC aZh(){return ffw.sgC;}}
 public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 fyZ.guX().a(new bbV());eZk carrier=eZk.a(null,null,null,fyW.ae((short)3702,(short)1));System.out.println("native3702 carrier rHv="+field(carrier,"rHv").getLong(carrier)+" rIY="+field(carrier,"rIY").getLong(carrier));
 System.out.println("native shL id="+ffw.shL.aKg()+" name="+ffw.shL.name());
 for(int ref:new int[]{416616,416790}){eVn d=bcA.dcX().AH(ref);System.out.print("ref="+ref+" criteria="+d.fKT()+" params="+d.fKJ()+" values=");for(int i=0;i<d.fKJ();i++)System.out.print(d.w(i,(short)1)+",");System.out.println();}
 eYs r=new eYs();r.b(bcA.dcX().AH(416616));r.C(null);
 PV a=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,v)->{if(m.getName().equals("b"))return v[0]==ffw.sgC?new Stat(60,100):v[0]==ffw.shL?new Stat(20,50):null;throw new UnsupportedOperationException(m.getName());});
 field(r,"bfs").set(r,a);field(r,"bfr").set(r,a);field(r,"rFC").setBoolean(r,true);field(r,"rFQ").setInt(r,0);

 eYn generic=new eYn();generic.b(bcA.dcX().AH(107312));generic.C(null);field(generic,"rFP").set(generic,ffw.sgC);field(generic,"bfs").set(generic,a);field(generic,"bfr").set(generic,a);field(generic,"rFC").setBoolean(generic,true);field(generic,"rFQ").setInt(generic,0);for(int mode=0;mode<=4;mode++){field(generic,"rFR").setInt(generic,mode);System.out.println("native913 mode="+mode+" override="+field(generic.d(null,false),"ryo").getInt(generic.d(null,false)));}

 for(int mode=0;mode<=4;mode++){field(r,"rFR").setInt(r,mode);eVt result=r.d(null,false);System.out.println("mode="+mode+" native override="+field(result,"ryo").getInt(result));}
 }
}
