import java.nio.file.Path;
/** Offline native minimal-item merge eligibility and maximum stack sizes. */
public class ExportItemStackRules {public static void main(String[]args)throws Exception{
apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
System.out.print("{\"source\":\"Native bIJ/fpC.bfi and fnR.n for two bare same-reference items\",\"items\":[");final boolean[] first={true};
apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO r){try{bJp tpl=new bIJ().f(r);fnR left=new fnR(1),right=new fnR(2);left.l(tpl);right.l(tpl);left.al((short)1);right.al((short)1);boolean merge=left.n(right);if(!first[0])System.out.print(",");first[0]=false;System.out.print("{\"reference\":"+r.d()+",\"maximum\":"+tpl.bfi()+",\"minimal_mergeable\":"+merge+"}");}catch(Throwable e){System.err.println("Skip"+r.d()+":"+e.getClass().getSimpleName());}}});System.out.println("]}");}}
