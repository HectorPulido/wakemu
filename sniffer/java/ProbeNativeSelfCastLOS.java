import java.util.*;import java.util.zip.*;
/** Native fcr cast-height LOS at same XYZ versus bare Sf catalog rays. */
public class ProbeNativeSelfCastLOS {
 static class Geometry extends VE {
  final List<VB> chunks=new ArrayList<>();int dynamicQueries;
  public VB aO(int x,int y){for(VB b:chunks)if(x>=b.bbn&&x<b.bbn+18&&y>=b.bbo&&y<b.bbo+18)return b;return null;}
  public VD aP(int x,int y){return null;}
  public boolean h(int x,int y,short z){dynamicQueries++;return false;}
 }
 public static void main(String[]args)throws Exception{
  Geometry map=new Geometry();try(ZipFile archive=new ZipFile("client/contents/maps/tplg/1134.jar")){
   for(var e:Collections.list(archive.entries()))if(e.getName().matches("-?\\d+_-?\\d+")){
    aoG r=aoG.dx(archive.getInputStream(e).readAllBytes());VB b=VC.ag(r.aJn());b.a(r);map.chunks.add(b);
   }
  }
  for(int height:new int[]{0,6,40}){
   map.dynamicQueries=0;boolean valid=fcr.a(-8,-7,(short)-1,height,-8,-7,(short)-1,6,map);
   System.out.println("self height="+height+" LOS="+valid+" queries="+map.dynamicQueries);
   if(!valid)throw new AssertionError("Native owncell cast rejects");
  }
 }
}
