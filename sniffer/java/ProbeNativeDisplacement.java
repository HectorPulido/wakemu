import java.lang.reflect.*;
import java.util.*;
import com.google.protobuf.Descriptors;
public class ProbeNativeDisplacement {
 static PV actor(int x,int y,int z){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class,fax.class},(p,m,a)->switch(m.getName()){
  case "bcz"->x;case "bcA"->y;case "bcB"->(short)z;case "bcy","baA"->aAS.wL(3);
  default->throw new UnsupportedOperationException(m.getName());});}
 static void set(Object o,Class<?>c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static void additional(Object effect,Class<?> owner)throws Exception{
  iP b=iN.QQ();Method m=owner.getDeclaredMethod("b",iP.class);m.setAccessible(true);m.invoke(effect,b);
  System.out.println(effect.getClass().getSimpleName()+" additional="+HexFormat.of().formatHex(b.QX().toByteArray()));
 }
 public static void main(String[]args)throws Exception{
  for(aAS d:List.of(aAS.dyA,aAS.dyu,aAS.dyy,aAS.dyw))System.out.println("specialdir="+d+" wp="+d.wp()+" vec="+d.dyJ+","+d.dyK);
  for(Class<?> c:List.of(eXK.class,eXJ.class))for(int[]xy:new int[][]{{4,0},{1,1},{2,1},{0,0}}){
   Object e=c.getConstructor().newInstance();set(e,Qe.class,"bfr",actor(0,0,0));set(e,Qe.class,"bfs",actor(xy[0],xy[1],0));set(e,eXD.class,"ckD",3);
   eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->switch(m.getName()){case "fKJ"->1;default->throw new UnsupportedOperationException(m.getName());});set(e,Qe.class,"bfp",def);
   Method endpoint=c.getDeclaredMethod("fOu");endpoint.setAccessible(true);aBn cell=(aBn)endpoint.invoke(e);
   System.out.println(c.getSimpleName()+" target="+Arrays.toString(xy)+" endpoint="+cell.getX()+","+cell.getY()+","+cell.bdn());
  }
  eZC teleport=new eZC();set(teleport,Qe.class,"bft",new aBn(-2,3,(short)-1));additional(teleport,eZB.class);
  eXK push=new eXK();set(push,eXD.class,"rEc",List.of(new aBn(2,0,(short)0),new aBn(3,0,(short)1)));additional(push,eXD.class);
  eXk swap=new eXk();set(swap,eXk.class,"nvt",4);set(swap,eXk.class,"nvu",5);set(swap,eXk.class,"rDe",(short)6);set(swap,eXk.class,"rDb",1);set(swap,eXk.class,"rDc",2);set(swap,eXk.class,"rDd",(short)3);additional(swap,eXk.class);
 }
}
