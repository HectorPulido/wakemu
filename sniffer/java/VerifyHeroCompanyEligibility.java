/** Executes real native company UI predicates on parsed account roster data.
 * Installs the decoded data model directly to omit graphics-dependent as callbacks. */
import java.nio.*;import java.nio.file.*;import java.lang.reflect.*;
public class VerifyHeroCompanyEligibility {
 static void set(Class<?> cls,Object target,String name,Object val)throws Exception{Field f=cls.getDeclaredField(name);f.setAccessible(true);f.set(target,val);}
 public static void main(String[]args)throws Exception{
 int status=0;
 try{
  byte[] company=Files.readAllBytes(Path.of(args[1]));
  long accountId=ByteBuffer.wrap(company).getLong(8);
  aTJ account=new aTJ();account.oh(accountId);aTx.cWt().a(account);
  eDP.foL().d(accountId,company);
  ByteBuffer buf=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));int count=Byte.toUnsignedInt(buf.get());
  for(int i=0;i<count;i++){
   byte[] blob=new byte[buf.getInt()];buf.get(blob);eHk data=new eHk();data.ew(blob);
   biB actor=new biB(false);set(eGj.class,actor,"aHm",data.fsS().Vc);set(bjo.class,actor,"ikv",data);
   biz.dpY().aq(actor);biz.dpY().f(actor,data.fvT().Wi);
   bit row=new bit(actor,null);
   if(!Boolean.TRUE.equals(row.eH("isInCompanyNation")) || !Boolean.TRUE.equals(row.eH("isInCompanyGuild")))
    throw new AssertionError("native company eligibility failed for actor "+actor.Sn());
   System.out.println("actor="+actor.Sn()+" class="+actor.getClass().getName()+" companyOwner="+actor.cBt()+" cachedNation="+biz.dpY().an(actor)+" guild="+actor.Ya()+" nationGate="+row.eH("isInCompanyNation")+" guildGate="+row.eH("isInCompanyGuild"));
  }
 }catch(Throwable e){status=1;e.printStackTrace();}finally{System.exit(status);}
 }
}
