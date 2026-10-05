import java.lang.reflect.*;import java.util.*;
public class ProbeNativeSpellGrant {
 static void set(Object o,Class<?>c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
  eWn runner=new eWn();set(runner,eWn.class,"hXV",5345);set(runner,eWn.class,"rAX",(short)-1);set(runner,eWn.class,"rAV",(byte)2);set(runner,eWn.class,"rAW",(short)0);
  iP out=iN.QQ();Method encode=eWn.class.getDeclaredMethod("b",iP.class);encode.setAccessible(true);encode.invoke(runner,out);iN wire=out.QX();ij additional=wire.QA();
  if(additional.getValue()!=5345||additional.tL()!=-1||additional.Mg()!=2||additional.Mi()!=0)throw new AssertionError("native additional");
  System.out.println("PASS eWn649 AdditionalDatas ref5345 level-1 bar2 slot0: "+HexFormat.of().formatHex(additional.toByteArray()));
 }
}
