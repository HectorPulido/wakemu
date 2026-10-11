import java.lang.reflect.Field;
import java.util.*;
import com.google.gson.GsonBuilder;
import org.antlr.runtime.ANTLRStringStream;
import org.antlr.runtime.CommonTokenStream;

/** Offline native predicate oracle: actual NPC and actual account-primary map. */
public class VerifyNativeHeroPrimary {
    static void field(Object actor,String name,long value)throws Exception {
        Field field=eGj.class.getDeclaredField(name);field.setAccessible(true);field.setLong(actor,value);
    }
    static amb criterion(String expression)throws Exception {
        eQd parser=new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(expression))));
        alS result=parser.fGw();
        if(parser.getNumberOfSyntaxErrors()!=0 || !(result instanceof amb))throw new AssertionError(expression);
        return (amb)result;
    }
    public static void main(String[]args)throws Exception {
        amb predicate=criterion("IsHero()");
        bje actor=new bje();List<Object>rows=new ArrayList<>();
        long[][] cases={{0,-200,0,0},{0,-200,1,-200},{99,42,0,0},{99,42,1,7},{99,42,1,42},{0,0,0,0}};
        try {
            for(long[] test:cases){
                fkJ.suE.clear();field(actor,"ePn",test[0]);field(actor,"aHm",test[1]);
                if(test[2]!=0)fkJ.suE.av(test[0],test[3]);
                boolean result=predicate.b(null,actor,null,null);
                long primary=fkJ.suE.sS(actor.Xi());
                if(result!=(primary!=actor.Sn()))throw new AssertionError("Predicate mismatch");
                rows.add(Map.of("account_id",actor.Xi(),"actor_id",actor.Sn(),"entry_present",fkJ.suE.sR(actor.Xi()),"primary",primary,"is_hero",result));
            }
            fkJ.suE.clear();fkJ.suE.av(99,42);fkJ.suE.sT(99);
            if(fkJ.suE.sS(99)!=0 || fkJ.suE.sR(99))throw new AssertionError("remove");
            fkJ.suE.av(99,42);fkJ.suE.ax(99,7);
            if(fkJ.suE.sS(99)!=42)throw new AssertionError("wrong actor removal");
            fkJ.suE.ax(99,42);
            if(fkJ.suE.sS(99)!=0)throw new AssertionError("matching actor removal");
            System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("rows",rows,"no_entry_primary",0,"remove_checks_passed",true)));
        }finally{fkJ.suE.clear();}
        System.exit(0);
    }
}
