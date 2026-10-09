import java.lang.reflect.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;
import org.antlr.runtime.*;
/** Original po decode/eGm apply/eNH predicate over actual eGz context. */
public class ProbeNativeAIControl {
 static eNH parse(String text) {
  eQd parser=new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(text))));
  ArrayList<alS> result=parser.fGv();
  if(parser.getNumberOfSyntaxErrors()!=0)throw new AssertionError(text);
  return (eNH)result.get(result.size()-1);
 }
 public static void main(String[] args)throws Exception {
  Field singleton=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");singleton.setAccessible(true);
  sun.misc.Unsafe unsafe=(sun.misc.Unsafe)singleton.get(null);
  eGj actor=(eGj)unsafe.allocateInstance(bje.class);
  Field field=eGj.class.getDeclaredField("pGC");field.setAccessible(true);field.set(actor,new eGz<>(){});
  Constructor<eGm> constructor=eGm.class.getDeclaredConstructor(eGj.class,po.class);constructor.setAccessible(true);
  eNH caster=parse("IsControlledByAI(\"caster\")"),target=parse("IsControlledByAI(\"TARGET\")");
  List<Map<String,Object>> rows=new ArrayList<>();
  for(byte wire:new byte[]{0,1,2,-1}) {
   po section=new po();section.aG(ByteBuffer.wrap(new byte[]{wire}));constructor.newInstance(actor,section).zm();
   boolean expected=wire==1;
   if(actor.fqL()!=expected || (caster.a(actor,null,null,null)==0)!=expected || (target.a(null,actor,null,null)==0)!=expected)throw new AssertionError("wire="+wire);
   rows.add(Map.of("wire",wire,"controlled_by_ai",actor.fqL()));
  }
  if(caster.a(null,null,null,null)!=-1)throw new AssertionError("null");
  eGj player=(eGj)unsafe.allocateInstance(biB.class);
  if(player.dpR() || !actor.dpR())throw new AssertionError("native baseline");
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("rows",rows,"predicate","eNH","producer","po.SX -> eGm.zm -> eGz.pHH","biB_dpR",player.dpR(),"bje_dpR",actor.dpR())));
  System.out.println("PASS original AI-control rows="+rows.size()+" + null target");
 }
}
