import java.lang.reflect.*;import java.util.*;
/** Original eXq.C/fOr and eXD path additional codec. */
public class ProbeNativeApproach {
 static int property=-1;
 static PV actor(){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class,fax.class,eHg.class},(p,m,a)->switch(m.getName()){
  case "bcz","bcA"->0;case "bcB"->(short)0;case "Sn"->7L;case "bcM"->(byte)0;case "buX"->false;
  case "a"->((PE)a[0]).aKg()==property;default->throw new UnsupportedOperationException(m.getName());});}
 static void set(Object object,Class<?>owner,String name,Object value)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(object,value);}
 public static void main(String[]args)throws Exception{
  for(int count:new int[]{0,1}){
   eXq effect=new eXq();set(effect,Qe.class,"bfr",actor());set(effect,Qe.class,"bft",new aBn(4,2,(short)9));
   eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){
    case "fKJ"->count;case "a"->a[0] instanceof eVl?false:3;default->throw new UnsupportedOperationException(m.getName());});
   set(effect,Qe.class,"bfp",def);effect.C(null);
   Field d=eXD.class.getDeclaredField("ckD");d.setAccessible(true);if(d.getInt(effect)!=(count==0?6:3))throw new AssertionError("native distance");
   if(!effect.fOr())throw new AssertionError("ordinary approach");property=71;if(effect.fOr())throw new AssertionError("CANT_GET_CLOSER");property=-1;
   set(effect,eXD.class,"rEc",List.of(new aBn(1,0,(short)0),new aBn(2,0,(short)1)));
   iP proto=iN.QQ();Method b=eXD.class.getDeclaredMethod("b",iP.class);b.setAccessible(true);b.invoke(effect,proto);
   byte[] bytes=proto.QX().toByteArray();if(args.length>0)java.nio.file.Files.write(java.nio.file.Path.of(args[0]),bytes);
  }
  System.out.println("Native eXq explicit/Manhattan distance, property71 and inherited path codec:6PASS");
 }
}
