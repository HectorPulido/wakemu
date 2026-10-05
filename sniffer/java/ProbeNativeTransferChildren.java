import java.nio.file.*;import java.util.*;
/** Actual native first/second definitions; no spell-specific execution policy. */
public class ProbeNativeTransferChildren {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<Integer,int[]> children=new HashMap<>();
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX row){children.put(row.d(),row.cku());}});
  for(String id:args){int reference=Integer.parseInt(id);eVn parent=bcA.dcX().AH(reference);
   System.out.println("parent="+reference+" family="+parent.awM()+" children="+Arrays.toString(children.get(reference)));
   for(int child:children.get(reference)){eVn e=bcA.dcX().AH(child);System.out.println("child="+child+" family="+e.awM()+" variant="+e.aZR()+" levels="+e.fKR()+".."+e.fKS()+" children="+Arrays.toString(children.get(child)));}
  }
 }
}
