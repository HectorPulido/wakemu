import java.nio.*;
/** Native wire/entitlement oracle; never starts a game session. */
public class VerifyHeroesProtocol {
 public static void main(String[] args)throws Exception{
  for(eEQ result:eEQ.values())System.out.println(result.aKg()+" "+result.name());
  if(new cnY(7L).d()!=12219||new cnZ(7L).d()!=12006||new Ou().d()!=1074)throw new AssertionError("request opcodes");
  cwC ack=new cwC();ack.dp(new byte[]{1});if(ack.bkq()!=eEQ.pfW.aKg()||ack.d()!=12587)throw new AssertionError("ack");
  eEI.oZx.a(eEL.pcq,"2");fkx eligibility=new fkx();eligibility.nc(true);eligibility.UY(0);
  if(fky.suy.a(eligibility)!=eEQ.pfW)throw new AssertionError("entitled empty");
  eligibility.UY(2);if(fky.suy.a(eligibility)!=eEQ.pga)throw new AssertionError("two hero cap");
  eligibility.nc(false);eligibility.UY(0);if(fky.suy.a(eligibility)!=eEQ.pga)throw new AssertionError("no entitlement");
  eSJ company=new eSJ();byte[] body=ByteBuffer.allocate(41).putLong(9).putLong(7).putInt(0).putLong(0).putInt(0).putInt(1).put((byte)1).array();company.a(9,ByteBuffer.wrap(body));if(!company.aPU()||company.dyK()!=7)throw new AssertionError("company activated/chief");
  System.out.println("PASS native heroes opcodes/ack, company activation, and entitlement cap");
 }
}
