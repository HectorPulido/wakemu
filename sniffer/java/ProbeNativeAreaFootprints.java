/** Original anc/amX footprint membership, including isotropic point and rings. */
public class ProbeNativeAreaFootprints {
 static boolean contains(anc area,int x,int y,int radius){
  return area.b(0,0,(short)0,3,0,(short)0,aAS.wL(1),x,y,(short)17,(byte)radius);
 }
 public static void main(String[]args){
  anc point=anD.bEz();anu circle=new anu();circle.p(new int[]{1});anH ring=new anH();ring.p(new int[]{1,1});
  for(anc area:new anc[]{point,circle,ring}){
   for(int[] row:new int[][]{{0,0,0},{1,0,0},{1,0,1},{2,0,1},{0,0,1},{2,2,1},{1,0,-1}})
    System.out.println(area.bEm()+" actor="+row[0]+","+row[1]+" radius="+row[2]+" ->"+contains(area,row[0],row[1],row[2]));
  }
  if(contains(point,1,0,0)||!contains(point,1,0,1))throw new AssertionError("point footprint");
  if(!contains(circle,2,0,1))throw new AssertionError("circle boundary footprint");
  if(contains(ring,0,0,0)||!contains(ring,0,0,1))throw new AssertionError("ring hole footprint");
  if(contains(point,1,0,-1))throw new AssertionError("signed negative radius");
  System.out.println("PASS original anc.b/amX.a isotropic physical footprints");
 }
}
