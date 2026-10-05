import java.util.*;import java.nio.*;
public class ProbeNativeInstanceCondition {
 public static void main(String[]args)throws Exception{
  ProbeNativeLevelGroup.Actor caster=new ProbeNativeLevelGroup.Actor(),target=new ProbeNativeLevelGroup.Actor();rE position=new rE();ByteBuffer payload=ByteBuffer.allocate(20);payload.putInt(3).putInt(-13).putShort((short)1).putLong(1385).put((byte)0).put((byte)0).flip();position.aG(payload);caster.fE(position.Vp);target.fE(527);
  eKB condition=new eKB(new ArrayList<>());
  if(condition.d(caster,target,null,null)!=1385||condition.d(null,target,null,null)!=527)throw new AssertionError("native actor property binding");
  caster.fE(-4000);if(condition.d(caster,target,null,null)!=-4000)throw new AssertionError("signedlong");
  try{condition.d(null,null,null,null);throw new AssertionError("unknownmusterror");}catch(alA expected){}
  System.out.println("PASS eKB/eII.l/eGj.arM: casterfE1385,targetfallback527,signedlong-4000,unknownerror");
 }
}
