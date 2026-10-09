import java.lang.reflect.*;

/** Original RC methods inherited by fyR: raw UID identity, no reference count. */
public final class ProbeNativeSpellGrantRegistry {
 static int checks;
 static void require(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
 static Rq object(long uid,int reference){
  return(Rq)Proxy.newProxyInstance(Rq.class.getClassLoader(),new Class[]{Rq.class},(p,m,a)->{
   return switch(m.getName()){
    case "LV"->uid;case "awe"->reference;case "bfh","bfi"->(short)1;
    case "bfl"->false;case "n"->false;case "bfj","bfk"->p;
    case "toString"->"spellUID="+uid;default->null;
   };
  });
 }
 public static void main(String[]args){
  RC<Rq,Object> book=new RC<Rq,Object>((short)100,null,null,false,false,false) {
   public int oZ(int reference){throw new UnsupportedOperationException("unused");}
   public int a(int reference,int count,boolean flag){throw new UnsupportedOperationException("unused");}
  };
  Rq base=object(100,100), granted=object(100,100);
  require(book.b(base),"register original raw book object");
  require(book.f(granted),"grant tests raw UID rather than new object identity");
  if(!book.f(granted))book.b(granted);
  require(book.dL(100)==base,"grant preserves existing raw object");
  require(book.c(granted),"remove by raw UID through grant object");
  require(book.dL(100)==null,"no reference count preserves base object");
  Rq replacement=object(100,100);require(book.b(replacement),"regrant new raw object");
  require(book.dL(100)==replacement,"removed source object is not resurrected");
  Rq packed=object((7L<<32)|100,100);require(book.b(packed),"packed player UID is distinct");
  require(book.c(replacement),"remove temporary raw object");
  require(book.dL((7L<<32)|100)==packed,"raw removal leaves packed progression object");
  System.out.println("PASS "+checks+" original RC/fyR UID lifecycle checks; no game catalogs loaded");
 }
}
