import java.nio.file.Path;
/** Raw native item fields used by fpC.gjv/ghe; names are kept obfuscated on purpose. */
public final class ExportNativeEnchantmentEligibility {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  System.out.print("{\"source\":\"Installed aLO.cpR/cpS -> bGT.bJq.gv/gw -> fpC.gq/gr; fpC.gjv tests both nonzero\",\"items\":[");
  final boolean[] first={true};
  apw.bGL().a(new aLO(),new apB<aLO>() { public void load(aLO raw) { try {
   bJp item=new bIJ().f(raw);
   if(!first[0])System.out.print(","); first[0]=false;
   System.out.print("{\"reference\":"+item.d()+",\"level\":"+item.cmZ()+",\"raw_cpR\":"+item.cpR()+",\"raw_cpS\":"+item.cpS()+",\"native_gjv_eligible\":"+item.gjv()+"}");
  } catch(Throwable failure) { System.err.println("Skipped item "+raw.d()+": "+failure.getClass().getSimpleName()); } }});
  System.out.println("]}");
 }
}
