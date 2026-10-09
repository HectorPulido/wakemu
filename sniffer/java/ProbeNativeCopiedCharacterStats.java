import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Original eHI source constructor with real ffh PA, independent of a fighter spawn. */
public final class ProbeNativeCopiedCharacterStats {
    static class Actor extends ProbeNativeLevelGroup.Actor {
        @Override public PA b(PC stat){return frm().b(stat);}
    }
    public static void main(String[] args) throws Exception {
        var field=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");field.setAccessible(true);
        var unsafe=(sun.misc.Unsafe)field.get(null);
        List<Object> output=new ArrayList<>();
        for(int percentage:new int[]{100,50,33,0,-1,125}){
            Actor actor=(Actor)unsafe.allocateInstance(Actor.class);actor.level=200;
            ffh source=new ffh();
            source.e(ffw.sgC).or(250);source.e(ffw.sgC).on(125);
            source.e(ffw.sgD).or(9);source.e(ffw.sgD).on(3);
            source.e(ffw.sgE).or(6);source.e(ffw.sgE).on(2);
            source.e(ffw.sgF).or(6);source.e(ffw.sgF).on(4);
            ProbeNativeLevelGroup.set(actor,eGj.class,"pGB",source);
            ProbeNativeLevelGroup.set(actor,eGj.class,"q","Actual source");
            ProbeNativeLevelGroup.set(actor,eGj.class,"lJL",eGE.PW(9));
            eHI copied=new eHI((short)9,"Actual source",125,(short)200,actor,percentage,null);
            tA rows=new tA();copied.pRU.a(rows);
            List<Object> stats=new ArrayList<>();
            for(tB row:rows.abi)stats.add(List.of(row.Sj&255,row.abj,row.abk,row.abl,row.abm));
            Map<String,Object> result=new LinkedHashMap<>();
            result.put("percentage",percentage);result.put("characteristics",stats);
            output.add(result);
        }
        System.out.println(new Gson().toJson(output));
        System.exit(0);
    }
}
