import java.util.*;import java.util.zip.*;
public class VerifyCombatDynamicLOS {
 static class Geometry extends ExportCombatLOS.MapGeometry {
  boolean blocked;
  public boolean h(int x,int y,short z){return blocked&&x==-13&&y==-10;}
 }
 public static void main(String[]args)throws Exception {
  Geometry g=new Geometry();try(ZipFile z=new ZipFile("client/contents/maps/tplg/1134.jar")){for(var e:Collections.list(z.entries()))if(e.getName().matches("-?\\d+_-?\\d+")){aoG r=aoG.dx(z.getInputStream(e).readAllBytes());VB b=VC.ag(r.aJn());b.a(r);g.chunks.add(b);}}
  Sf ray=Sf.bfW();ray.a(g);ray.k(-14,-10,(short)-1);ray.l(-11,-10,(short)-1);if(!ray.bfZ())throw new AssertionError();
  g.blocked=true;ray.k(-14,-10,(short)-1);ray.l(-11,-10,(short)-1);if(ray.bfZ())throw new AssertionError();ray.bal();
  System.out.println("Native Sf rejects explicit intermediate dynamic blocker; clear ray accepted");
 }
}
