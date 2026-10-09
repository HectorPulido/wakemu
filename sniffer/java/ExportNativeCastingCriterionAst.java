import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
import org.antlr.runtime.*;

/** Original eQb/eQd parse-only AST snapshots; never invokes a criterion provider. */
public final class ExportNativeCastingCriterionAst {
    static final Gson GSON = new GsonBuilder().serializeNulls().create();
    static class Snapshot {
        final IdentityHashMap<alS,Integer> identities = new IdentityHashMap<>();
        final List<Map<String,Object>> nodes = new ArrayList<>();
        Object value(Object value) throws Exception {
            if(value==null || value instanceof String || value instanceof Number || value instanceof Boolean)
                return value;
            if(value instanceof Enum<?> e) return Map.of("enum_class",e.getDeclaringClass().getName(),"name",e.name());
            if(value instanceof alS criterion) return Map.of("node",node(criterion));
            if(value instanceof gnu.trove.list.array.TShortArrayList list)
                return value(list.toArray());
            if(value instanceof Collection<?> list) {
                List<Object> result=new ArrayList<>();for(Object item:list)result.add(value(item));return result;
            }
            if(value.getClass().isArray()) {
                List<Object> result=new ArrayList<>();for(int i=0;i<Array.getLength(value);i++)result.add(value(Array.get(value,i)));return result;
            }
            if(value instanceof Map<?,?> map) {
                List<Object> result=new ArrayList<>();
                for(var item:map.entrySet())result.add(Arrays.asList(value(item.getKey()),value(item.getValue())));
                return Map.of("map_entries",result);
            }
            return Map.of("unexpanded_class",value.getClass().getName());
        }
        int node(alS criterion) throws Exception {
            if(identities.containsKey(criterion))return identities.get(criterion);
            int identity=nodes.size();identities.put(criterion,identity);
            Map<String,Object> row=new LinkedHashMap<>();nodes.add(row);
            row.put("id",identity);row.put("class",criterion.getClass().getName());
            row.put("native_type",value(criterion.bDt()));row.put("native_opcode",value(criterion.bDq()));
            Map<String,Object> fields=new TreeMap<>();
            for(Class<?> type=criterion.getClass();type!=null && type!=Object.class;type=type.getSuperclass())
                for(Field field:type.getDeclaredFields()) {
                    if(Modifier.isStatic(field.getModifiers()) || field.isSynthetic())continue;
                    field.setAccessible(true);fields.put(type.getName()+"."+field.getName(),value(field.get(criterion)));
                }
            row.put("fields",fields);
            Method signature=alS.class.getDeclaredMethod("bDC");signature.setAccessible(true);
            row.put("declared_argument_signatures",value(signature.invoke(criterion)));
            return identity;
        }
    }
    static Map<String,Object> parse(String expression) {
        Map<String,Object> result=new LinkedHashMap<>();
        // Exact eQe.tx normalization and fGv statement entry point used by bPS.
        String normalized=expression.replaceAll("[\\r\\n]", "");
        eQb lexer=new eQb(new ANTLRStringStream(normalized));
        CommonTokenStream tokens=new CommonTokenStream(lexer);eQd parser=new eQd(tokens);
        try {
            List<alS> statements=parser.fGv();tokens.fill();
            alS root=null;
            if(statements!=null)for(alS statement:statements)
                if(statement!=null && statement.bDt()==alU.cHh)
                    root=root==null ? statement : alr.b(root,statement);
            if(root==null && statements!=null && !statements.isEmpty())root=statements.get(statements.size()-1);
            result.put("lexer_errors",lexer.getNumberOfSyntaxErrors());
            result.put("parser_errors",parser.getNumberOfSyntaxErrors());
            result.put("consumed_all",tokens.LA(1)==Token.EOF);
            if(root==null || lexer.getNumberOfSyntaxErrors()!=0 || parser.getNumberOfSyntaxErrors()!=0)
                throw new IllegalArgumentException("Native criterion parse failed");
            Snapshot snapshot=new Snapshot();result.put("root",snapshot.node(root));
            List<Integer> statementIds=new ArrayList<>();
            for(alS statement:statements)statementIds.add(statement==null ? null : snapshot.node(statement));
            result.put("statements",statementIds);result.put("nodes",snapshot.nodes);
            result.put("entry_point","eQe.tx/eQd.fGv; eQe.tz boolean conjunction");
            result.put("classes",new TreeSet<>(snapshot.nodes.stream().map(n->(String)n.get("class")).toList()));
            result.put("success",true);
        } catch(Throwable error) {
            result.put("success",false);result.put("error",error.toString());
            result.put("lexer_errors",lexer.getNumberOfSyntaxErrors());
            result.put("parser_errors",parser.getNumberOfSyntaxErrors());
        }
        return result;
    }
    static List<Map<String,Object>> calls(String expression, Set<String> names) {
        List<Map<String,Object>> result=new ArrayList<>();
        eQb lexer=new eQb(new ANTLRStringStream(expression));CommonTokenStream stream=new CommonTokenStream(lexer);
        stream.fill();List<?> tokens=stream.getTokens();
        for(int i=0;i+1<tokens.size();i++) {
            CommonToken token=(CommonToken)tokens.get(i);
            if(!names.contains(token.getText()))continue;
            int opening=i+1;
            while(opening<tokens.size() && ((Token)tokens.get(opening)).getChannel()!=Token.DEFAULT_CHANNEL)opening++;
            if(opening>=tokens.size() || !"(".equals(((Token)tokens.get(opening)).getText()))continue;
            int depth=0,closing=-1;
            List<String> arguments=new ArrayList<>();int argumentStart=((CommonToken)tokens.get(opening)).getStopIndex()+1;
            for(int j=opening;j<tokens.size();j++) {
                CommonToken part=(CommonToken)tokens.get(j);if(part.getChannel()!=Token.DEFAULT_CHANNEL)continue;
                if("(".equals(part.getText()))depth++;
                else if(")".equals(part.getText())) {
                    if(--depth==0) {
                        String argument=expression.substring(argumentStart,part.getStartIndex()).trim();
                        if(!argument.isEmpty() || !arguments.isEmpty())arguments.add(argument);
                        closing=j;break;
                    }
                } else if(",".equals(part.getText()) && depth==1) {
                    arguments.add(expression.substring(argumentStart,part.getStartIndex()).trim());
                    argumentStart=part.getStopIndex()+1;
                }
            }
            Map<String,Object> call=new LinkedHashMap<>();call.put("name",token.getText());
            call.put("start",token.getStartIndex());
            if(closing<0)call.put("error","Unclosed original lexer call tokens");
            else {
                int end=((CommonToken)tokens.get(closing)).getStopIndex()+1;
                String raw=expression.substring(token.getStartIndex(),end);
                call.put("end",end);call.put("expression",raw);call.put("arguments_raw",arguments);call.put("arity",arguments.size());
                Map<String,Object> parsed=parse(raw);call.put("native_parse",parsed);
                if(Boolean.TRUE.equals(parsed.get("success"))) {
                    List<?> nodes=(List<?>)parsed.get("nodes");
                    Map<?,?> root=(Map<?,?>)nodes.get((Integer)parsed.get("root"));
                    call.put("native_class",root.get("class"));
                    call.put("declared_argument_signatures",root.get("declared_argument_signatures"));
                }
            }
            result.add(call);
        }
        return result;
    }
    public static void main(String[] args)throws Exception {
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(System.in,java.nio.charset.StandardCharsets.UTF_8))) {
            for(String line;(line=reader.readLine())!=null;) {
                JsonObject input=JsonParser.parseString(line).getAsJsonObject();
                Map<String,Object> row=new LinkedHashMap<>();
                for(String key:new String[]{"expression_id","spell_id","location","expression_sha256","expression"})
                    row.put(key,GSON.fromJson(input.get(key),Object.class));
                row.put("spell_id",input.get("spell_id").getAsInt());
                String expression=input.get("expression").getAsString();Set<String> names=new HashSet<>();
                for(JsonElement name:input.getAsJsonArray("function_names"))names.add(name.getAsString());
                row.put("native_parse",parse(expression));row.put("calls",calls(expression,names));
                System.out.println(GSON.toJson(row));
            }
        }
    }
}
