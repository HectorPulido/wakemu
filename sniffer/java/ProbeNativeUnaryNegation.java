import java.io.*;
import java.util.*;
import com.google.gson.*;
import org.antlr.runtime.*;
/** Original eQb/eQd unary ! versus textual not, no combat catalog evaluation. */
public final class ProbeNativeUnaryNegation {
    public static void main(String[]args)throws Exception {
        Gson gson=new GsonBuilder().serializeNulls().create();
        BufferedReader reader=new BufferedReader(new InputStreamReader(System.in));
        for(String line;(line=reader.readLine())!=null;) {
            JsonObject input=JsonParser.parseString(line).getAsJsonObject();String source=input.get("source").getAsString();
            Map<String,Object> output=new LinkedHashMap<>();output.put("source",source);
            try {
                eQb lexer=new eQb(new ANTLRStringStream(source));CommonTokenStream tokens=new CommonTokenStream(lexer);tokens.fill();
                List<Object> tokenRows=new ArrayList<>();for(Object value:tokens.getTokens()){Token token=(Token)value;tokenRows.add(Map.of("type",token.getType(),"text",token.getText()));}
                output.put("tokens",tokenRows);
                eQd parser=new eQd(tokens);ArrayList<alS> criteria=parser.fGv();
                if(parser.getNumberOfSyntaxErrors()!=0||lexer.getNumberOfSyntaxErrors()!=0||criteria.isEmpty())throw new IllegalArgumentException("Native parse failed");
                alS criterion=criteria.get(criteria.size()-1);output.put("native_class",criterion.getClass().getName());
                output.put("value",input.has("evaluate")&& !input.get("evaluate").getAsBoolean()?null:((amb)criterion).b(null,null,null,null));
            } catch(Throwable error){output.put("error",error.toString());}
            System.out.println(gson.toJson(output));
        }
    }
}
