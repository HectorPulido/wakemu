import java.nio.*;import java.nio.file.*;
public class VerifyOwnTransport{public static void main(String[]a)throws Exception{ByteBuffer b=ByteBuffer.wrap(Files.readAllBytes(Path.of(a[0])));fzy d=new fzy();d.a(1,b);if(!d.b(zP.apn).contains(123)||!d.b(zP.apo).contains(456)||b.remaining()!=0)throw new AssertionError();System.out.println("Native fzy own ZAAP/DRAGO decode OK");}}
