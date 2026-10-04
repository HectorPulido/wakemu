import java.util.*;import java.util.zip.*;import com.google.gson.*;
/** Offline cardinal surface transitions through the original Sm algorithm. */
public class ExportCombatEdges{
 public static void main(String[]args)throws Exception{
  if(args.length!=7)throw new IllegalArgumentException("map xmin ymin xmax ymax moverHeight jumpCapacity");
  int map=Integer.parseInt(args[0]),xmin=Integer.parseInt(args[1]),ymin=Integer.parseInt(args[2]),xmax=Integer.parseInt(args[3]),ymax=Integer.parseInt(args[4]),height=Integer.parseInt(args[5]),jump=Integer.parseInt(args[6]);
  Map<String,Vy[]> surfaces=new HashMap<>();List<VB>chunks=new ArrayList<>();
  try(ZipFile archive=new ZipFile("client/contents/maps/tplg/"+map+".jar")){for(var e:Collections.list(archive.entries())){if(!e.getName().matches("-?\\d+_-?\\d+"))continue;aoG r=aoG.dx(archive.getInputStream(e).readAllBytes());VB b=VC.ag(r.aJn());b.a(r);chunks.add(b);}}
  for(int y=ymin;y<=ymax;y++)for(int x=xmin;x<=xmax;x++)for(VB b:chunks){if(x<b.bbn||x>=b.bbn+18||y<b.bbo||y>=b.bbo+18)continue;Vy[]c=Vy.blX();int n=b.a(x,y,c,0);surfaces.put(x+","+y,Arrays.copyOf(c,n));break;}
  List<Object>edges=new ArrayList<>();Sm policy=new Sm(height,(byte)0,jump,true);
  for(var entry:surfaces.entrySet()){Vy[]from=entry.getValue();for(int i=0;i<from.length;i++){Vy src=from[i];if(src.bLD<0||src.bLf)continue;for(int[]delta:new int[][]{{1,0},{-1,0},{0,1},{0,-1}}){Vy[]to=surfaces.get((src.bbn+delta[0])+","+(src.bbo+delta[1]));if(to==null||to.length==0)continue;int n=policy.a(i,0,from.length,from,0,to.length,to);for(int k=0;k<n;k++){Vy dst=to[policy.boE[k]];edges.add(new int[][]{{src.bbn,src.bbo,src.bbl},{dst.bbn,dst.bbo,dst.bbl}});}}}}
  System.out.println(new Gson().toJson(Map.of("map_id",map,"mover_height",height,"jump_capacity",jump,"cardinal_only",true,"limits","Static Sm geometry; dynamic entities/furniture and diagonal corner constraints excluded.","edges",edges)));
 }
}
