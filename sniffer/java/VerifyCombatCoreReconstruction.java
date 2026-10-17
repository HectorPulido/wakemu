import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;

/** Detached original readers and timeline enrollment. No server serializers. */
public final class VerifyCombatCoreReconstruction {
    static Path output;
    static final int FIGHT=99;
    static final long OWNER=22, ENEMY=-33, SUMMON=901;
    interface Writer { void write(DataOutputStream out) throws Exception; }
    static byte[] bytes(Writer writer) throws Exception {
        var buffer=new ByteArrayOutputStream(); var out=new DataOutputStream(buffer);
        writer.write(out); out.flush(); return buffer.toByteArray();
    }
    static void save(String name,byte[] value)throws Exception{Files.write(output.resolve(name+".bin"),value);}
    static void check(boolean good,String label){if(!good)throw new AssertionError(label);}
    static byte[] timeline(boolean full)throws Exception{
        long[] ids=full?new long[]{OWNER,SUMMON,ENEMY}:new long[]{OWNER,ENEMY};
        return bytes(out->{out.writeShort(full?2:0);out.writeInt(full?13:0);out.writeByte(full?1:0);out.writeLong(full?31000:0);
            for(int x=0;x<2;x++){out.writeByte(ids.length);for(long id:ids)out.writeLong(id);}
            out.writeByte(ids.length);for(long id:ids){out.writeLong(id);out.writeShort(full?(id==SUMMON?3:id==OWNER?4:2):0);}
            out.writeByte(full?1:-1);out.writeByte(0);out.writeByte(ids.length);for(long id:ids){out.writeLong(id);out.writeInt(0);}
        });
    }
    static byte[] bootstrap(byte[] state,boolean spectator,byte[] bonus)throws Exception{return bootstrap(state,spectator,bonus,false);}
    static byte[] bootstrap(byte[] state,boolean spectator,byte[] bonus,boolean declareSummon)throws Exception{
        return bytes(out->{out.writeInt(FIGHT);out.writeByte(spectator?2:1);out.writeLong(1134);out.writeLong(46);out.writeLong(-300);
            out.writeInt(0);out.writeShort(state.length);out.write(state);out.writeLong(OWNER);out.writeLong(ENEMY);out.writeBoolean(false);
            out.writeByte(declareSummon?3:2);for(long id:declareSummon?new long[]{OWNER,ENEMY,SUMMON}:new long[]{OWNER,ENEMY}){out.writeLong(id);out.writeByte(id==OWNER?0:1);out.writeByte(id==ENEMY?1:0);out.writeByte(1);out.writeShort(0);out.writeShort(0);}
            out.writeByte(0);out.writeByte(0);out.writeByte(0);out.writeInt(0);
            if(spectator){out.writeByte(2);out.writeInt(bonus.length);out.write(bonus);}
        });
    }
    static Tc table(){
        fce source=(fce)Proxy.newProxyInstance(fce.class.getClassLoader(),new Class[]{fce.class},(o,m,a)->m.getName().equals("d")?FIGHT:null);
        fev stats=(fev)Proxy.newProxyInstance(fev.class.getClassLoader(),new Class[]{fev.class},(o,m,a)->m.getName().equals("rI")?false:0);
        return new Tc(new feq(source,stats));
    }
    static int load(Tc table,byte[] state){ByteBuffer b=ByteBuffer.wrap(state);b.getShort();b.getInt();int phase=b.get();b.getLong();table.clear();table.a(null,b);return phase;}
    static void birth(Tc table){SQ options=new SQ();options.a(SR.pv(0));options.pt(0);options.ej(OWNER);table.a(SUMMON,(short)0,options);}
    static long count(Tc table){return Arrays.stream(table.bsw.bhH().toArray()).filter(id->id==SUMMON).count();}
    static class Step extends aET {final Runnable op;Step(Runnable op){super(1,0,0);this.op=op;}protected long cby(){op.run();return 0;}protected void cbj(){}}
    static byte[] varint(long value){var out=new ByteArrayOutputStream();do{int bits=(int)(value&127);value>>>=7;out.write(bits|(value==0?0:128));}while(value!=0);return out.toByteArray();}
    static byte[] field(int key,long value)throws Exception{return bytes(out->{out.write(varint(key<<3));out.write(varint(value));});}
    static byte[] blob(int key,byte[] value)throws Exception{return bytes(out->{out.write(varint((key<<3)|2));out.write(varint(value.length));out.write(value);});}
    static byte[] concat(byte[]...values)throws Exception{return bytes(out->{for(byte[] value:values)out.write(value);});}
    static byte[] summon(long creature,boolean self,boolean noTimeline)throws Exception{
        byte[] descriptor=bytes(out->{out.writeBoolean(self);out.writeShort(3251);out.writeShort(0);out.writeInt(-1);out.writeLong(creature);out.writeShort(20);out.writeByte(17);out.writeBoolean(false);out.writeBoolean(false);out.writeInt(3);out.writeLong(-1);out.writeBoolean(false);out.writeShort(noTimeline?1:0);if(noTimeline){out.writeByte(114);out.writeByte(1);}out.writeByte(0);out.writeLong(OWNER);out.writeInt(0);out.writeByte(0);});
        return concat(field(1,creature+1),field(2,creature+1),field(3,123),field(4,3251),field(6,OWNER),blob(8,blob(1,descriptor)),blob(12,field(4,creature)));
    }
    public static void main(String[] args)throws Exception{
        output=Path.of(args[0]);Files.createDirectories(output);eGM.a(null);
        byte[] initial=timeline(false),full=timeline(true);save("timeline-initial",initial);save("timeline-full",full);
        feN bonuses=new feN();bonuses.Ag(3);bonuses.ac(OWNER,7);bonuses.ac(ENEMY,9);bonuses.rP(ENEMY);bonuses.e(4,Collections.emptyList());bonuses.fZb().put(5,Collections.emptyList());byte[] bonus=bonuses.TM(0);save("bonus-native",bonus);
        byte[] owner=bootstrap(initial,false,bonus),spectator=bootstrap(initial,true,bonus);
        cvb cvb=new cvb();check(cvb.dp(owner)&&cvb.bhe()==FIGHT&&cvb.eHa()==2,"cvb admission");save("12847",owner);
        cva cva=new cva();check(cva.dp(spectator)&&cva.bhe()==FIGHT&&cva.eHn()==2,"cva spectator");feN decoded=new feN();decoded.dT(cva.eHo());check(decoded.rJ(OWNER)==7&&decoded.rJ(ENEMY)==9&&!decoded.rK(ENEMY),"native feN snapshot");save("12044",spectator);byte[] spectatorRoster=bootstrap(initial,true,bonus,true);cva declared=new cva();check(declared.dp(spectatorRoster)&&declared.eHa()==3,"spectator declared roster reference");save("12044-roster-summon",spectatorRoster);
        Tc old=table();load(old,full);birth(old);check(count(old)==2,"full-before-birth native duplicate");
        Tc corrected=table();check(load(corrected,initial)==0&&corrected.bik()==-1&&count(corrected)==0,"INITIAL no current");
        aER queue=new aER();queue.c(new Step(()->birth(corrected)));queue.cbu();check(queue.cbt().isEmpty()&&count(corrected)==1,"original queued birth completed once");
        check(load(corrected,full)==1&&count(corrected)==1&&corrected.bil()==SUMMON&&corrected.biw().big()==3,"native recovery current and progress");
        byte[] envelope=bytes(out->{out.writeByte(1);out.writeByte(0);out.writeInt(6);out.writeByte(0);out.writeShort(full.length);out.write(full);});
        byte[] recovery=bytes(out->{out.writeInt(FIGHT);out.writeShort(envelope.length);out.write(envelope);});cvn cvn=new cvn();check(cvn.dp(recovery)&&Arrays.equals(cvn.eHJ(),envelope),"cvn recovery envelope");save("12053",recovery);
        Map<String,Object> observations=new LinkedHashMap<>();observations.put("completed_normally",true);observations.put("fight",FIGHT);observations.put("owner",OWNER);observations.put("summon",SUMMON);observations.put("current",corrected.bil());observations.put("progress",corrected.biw().big());observations.put("old_duplicate_count",count(old));observations.put("completed_birth_count",1);observations.put("recovered_count",count(corrected));
        for(boolean self:new boolean[]{false,true})for(boolean noTimeline:new boolean[]{false,true}){
            byte[] proto=summon(SUMMON,self,noTimeline);eZl nativeRunner=new eZl();nativeRunner.lV(307);nativeRunner.ds(proto);
            check(nativeRunner.LV()==902&&nativeRunner.rHG.fwV()==SUMMON&&nativeRunner.rHG.dsr()==3251&&nativeRunner.rHG.cmZ()==20&&nativeRunner.rHI==self&&nativeRunner.hwX.bht()==OWNER,"native eZl descriptor and SQ");
            byte[] packet=bytes(out->{out.writeInt(FIGHT);out.writeInt(7);out.writeInt(-1);out.writeBoolean(true);out.writeInt(307);out.writeShort(proto.length);out.write(proto);});cvX application=new cvX();check(application.dp(packet)&&application.awM()==307&&application.eIK(),"cvX immediate summon");
            save("12613-self"+(self?1:0)+"-pb"+(noTimeline?1:0),packet);
        }
        byte[] repeated=bytes(out->{out.writeShort(2);out.writeInt(13);out.writeByte(1);out.writeLong(31000);out.writeByte(4);for(long id:new long[]{OWNER,SUMMON,SUMMON,ENEMY})out.writeLong(id);out.writeByte(3);for(long id:new long[]{OWNER,SUMMON,ENEMY})out.writeLong(id);out.writeByte(3);for(long id:new long[]{OWNER,SUMMON,ENEMY}){out.writeLong(id);out.writeShort(id==SUMMON?3:2);}out.writeByte(1);out.writeByte(0);out.writeByte(3);for(long id:new long[]{OWNER,SUMMON,ENEMY}){out.writeLong(id);out.writeInt(0);}});
        Tc repeatedTable=table();load(repeatedTable,repeated);check(count(repeatedTable)==2&&repeatedTable.bil()==SUMMON&&repeatedTable.biw().big()==3,"native repeated available member format");save("timeline-repeated",repeated);observations.put("repeated_available_count",count(repeatedTable));
        byte[] second=summon(902,false,false);eZl secondRunner=new eZl();secondRunner.lV(307);secondRunner.ds(second);check(secondRunner.rHG.fwV()==902&&secondRunner.LV()==903,"second native actor descriptor");save("12613-second-actor",bytes(out->{out.writeInt(FIGHT);out.writeInt(7);out.writeInt(-1);out.writeBoolean(true);out.writeInt(307);out.writeShort(second.length);out.write(second);}));
        byte[] emptyBonus=new feN().TM(0); // Replace its default period with an explicit native3 below.
        feN empty=new feN();empty.Ag(3);emptyBonus=empty.TM(0);final byte[] typed=emptyBonus;
        byte[] phase=bytes(out->{out.writeInt(FIGHT);out.writeByte(2);out.writeInt(0);out.writeLong(31000);out.writeInt(typed.length);out.write(typed);out.writeByte(0);out.writeInt(10);out.write(new byte[10]);out.writeInt(2);out.writeShort(0);});cvx cvx=new cvx();boolean phaseReturn=cvx.dp(phase);check(!phaseReturn&&cvx.eHn()==2&&cvx.eHW()==0&&cvx.eHX()==31000&&Arrays.equals(cvx.eHo(),typed),"cvx ACTION phase");observations.put("cvx_dp_return",phaseReturn);save("12514",phase);
        save("13420",ByteBuffer.allocate(4).putInt(FIGHT).array());
        Files.writeString(output.resolve("observations.json"),VerifyCombatReconstructionSlice.json(observations));
        System.out.println("PASS original cvb/cva/feN/cvn/cvx/eZl/Tc/aER independent core fixtures");
    }
}
