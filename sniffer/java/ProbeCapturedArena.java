import java.nio.*;
import java.nio.file.*;
public class ProbeCapturedArena {
  static class Grid extends QI {
    void add(VB chunk) { bMf.add(new VD(chunk)); }
  }
  public static void main(String[] args) throws Exception {
    VF.dd("jar:file:"+Path.of("client/contents/maps/tplg").toAbsolutePath()+"/%d.jar!/");
    Grid q=new Grid();new fct(q).eO(ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0]))));
    for(int[] xy:new int[][]{{-10,-3},{-9,-4},{-9,-2},{-9,-3}}) {
      int x=xy[0],y=xy[1];
      System.out.println(x+","+y+" height="+q.X(x,y)+" selected="+q.j(x,y,(short)-1)+" maskOption="+q.Z(x,y)+" P="+q.P(x,y)+" Q="+q.Q(x,y)+" R="+q.R(x,y)+" arena="+q.aK(x,y)+" occupants="+q.U(x,y));
    }
  }
}
