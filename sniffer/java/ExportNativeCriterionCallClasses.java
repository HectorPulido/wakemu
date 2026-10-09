import java.io.*;
import java.util.*;
import com.google.gson.*;
import org.antlr.runtime.*;

/** Parse isolated calls with the original eQb/eQd, without evaluating criteria. */
public class ExportNativeCriterionCallClasses {
    public static void main(String[] args) throws Exception {
        Gson gson = new Gson();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            for (String line; (line = reader.readLine()) != null;) {
                JsonObject input = JsonParser.parseString(line).getAsJsonObject();
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("name", input.get("name").getAsString());
                result.put("expression", input.get("expression").getAsString());
                try {
                    eQb lexer = new eQb(new ANTLRStringStream(input.get("expression").getAsString()));
                    eQd parser = new eQd(new CommonTokenStream(lexer));
                    alS criterion = parser.fGw();
                    if (criterion == null || parser.getNumberOfSyntaxErrors() != 0
                            || lexer.getNumberOfSyntaxErrors() != 0) {
                        throw new IllegalArgumentException("Native criterion parse failed");
                    }
                    result.put("native_class", criterion.getClass().getName());
                } catch (Throwable error) {
                    result.put("native_class", null);
                    result.put("error", error.toString());
                }
                System.out.println(gson.toJson(result));
            }
        }
    }
}
