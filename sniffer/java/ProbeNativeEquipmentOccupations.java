import java.nio.file.*;import java.util.*;
public class ProbeNativeEquipmentOccupations {public static void main(String[]args){
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");final bJp[] tpl={null};apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO r){if(r.d()==2027)tpl[0]=new bIJ().f(r);}});
 fnR item=new fnR(101);item.l(tpl[0]);item.al((short)1);fnO main=fnO.gf((byte)15),secondary=fnO.gf((byte)16);
 Set<fnO> occupied=fop.b(new fnZ(),item,main);if(!occupied.equals(Set.of(main,secondary)))throw new AssertionError(occupied);
 fpj selected=new fpj();selected.c(main,101L);fpj decoded=fpi.eN(fpi.f(selected));if(decoded.geO().size()!=1||decoded.t(main)!=101L||decoded.t(secondary)!=null)throw new AssertionError(decoded.geO());
 System.out.println("PASS native2027: occupiedslots15/16, sheet codec stores only realUID101 in15, no fabricated secondary cloneUID");
}}
