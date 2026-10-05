import java.lang.reflect.*;
/** Actual eYz callback and eVt.SQ value transport, independent of HP deltas. */
public class ProbeNativeTransferCallback {
 static void set(Object o,Class<?> owner,String name,Object value)throws Exception {
  Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(o,value);
 }
 public static void main(String[]args)throws Exception {
  eYy group=new eYy();eVt context=new eVt();
  Constructor<?> ctor=eYz.class.getDeclaredConstructors()[0];ctor.setAccessible(true);
  eVz callback=(eVz)ctor.newInstance(group,context);
  Field accumulator=eYy.class.getDeclaredField("rGj");accumulator.setAccessible(true);
  int[] values=(int[])accumulator.get(group);
  eXE child=new eXE();
  for(int[] row:new int[][]{{0,7,7},{7,0,7},{7,-3,-3}}) {
   values[0]=row[0];set(child,Qe.class,"aSg",row[1]);context.a(callback);
   callback.h(child);
   if(values[0]!=row[2]||context.aZi().contains(callback))
    throw new AssertionError("eYz nonzero capture/self removal");
  }
  values[0]=7;set(child,Qe.class,"aSg",-3);callback.i(child);
  if(values[0]!=7)throw new AssertionError("i must not capture");
  context.SP(20);context.SQ(17);
  if(context.Oh()!=20||context.Ol()!=17)throw new AssertionError("SQ value must not overwrite SP level");
  if(args.length>0) java.nio.file.Files.write(java.nio.file.Path.of(args[0]),context.fLV().toByteArray());
  if(args.length>1) {
   eVt received=new eVt();received.f(ir.ba(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[1]))));
   if(received.Oh()!=20||received.Ol()!=17||received.ban())
    throw new AssertionError("server SQ context must preserve level/value and disable mb");
  }
  // eZR.n calls C before applying the context's forced value.
  eXE forced=new eXE();set(forced,Qe.class,"bfu",context);forced.n(null);
  if(forced.getValue()!=17)throw new AssertionError("eZR.n must apply SQ after C");
  Method override=eZR.class.getDeclaredMethod("a",eVt.class);override.setAccessible(true);
  for(int[] row:new int[][]{{3,50,1},{-3,50,1},{9,50,4},{Integer.MAX_VALUE,100,1}}) {
   set(forced,Qe.class,"aSg",row[0]);context.a(row[1],eVu.ryw);override.invoke(forced,context);
   if(forced.getValue()!=row[2])throw new AssertionError("native percent int overflow/truncation/min1");
  }
  System.out.println("PASS native eYz nonzero/zero/negative capture, self removal, i no-op, SQ distinct from SP");
 }
}
