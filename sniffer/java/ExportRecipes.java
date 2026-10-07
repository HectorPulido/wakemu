import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;

/** Export the installed client's raw recipe table through its native apw/aNh reader. */
public final class ExportRecipes {
    public static void main(String[] args) throws Exception {
        String bdata = Path.of("client/contents/bdata").toAbsolutePath().toString();
        apw.bGL().dd("jar:file:" + bdata + "/%d.jar!/%d.bin");
        List<Map<String, Object>> recipes = new ArrayList<>();
        List<Map<String, Object>> errors = new ArrayList<>();
        List<Map<String, Object>> tableDefinitions = new ArrayList<>();
        List<Map<String, Object>> definitionErrors = new ArrayList<>();
        List<Map<String, Object>> tableInstances = new ArrayList<>();
        List<Map<String, Object>> tableInstanceErrors = new ArrayList<>();
        Map<Integer, Map<String, Object>> definitionsById = new HashMap<>();
        Set<Integer> usedDefinitionIds = new HashSet<>();
        Map<Integer, Integer> professionByRecipe = new HashMap<>();
        int[] counts = new int[3];
        int[] definitionCounts = new int[1];

        apw.bGL().a(new aNh(), new apB<aNh>() {
            @Override
            public void load(aNh raw) {
                counts[0]++;
                try {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("recipe_id", raw.d());
                    row.put("profession_id", raw.cjG());
                    professionByRecipe.put(raw.d(), raw.cjG());
                    row.put("minimum_level", raw.tL());
                    row.put("raw_duration", raw.Tz());
                    row.put("raw_clT", raw.clT());
                    row.put("raw_cvc", raw.cvc());
                    row.put("raw_cvd", raw.cvd());
                    row.put("raw_ckE", raw.ckE());
                    row.put("raw_cve", raw.cve());
                    row.put("raw_cvf", raw.cvf());
                    row.put("raw_cvg", raw.cvg());
                    row.put("raw_cvh", raw.cvh());
                    row.put("raw_cvi", raw.cvi());
                    row.put("raw_pf", raw.pf());
                    row.put("raw_cvj", raw.cvj());

                    List<Map<String, Object>> ingredients = new ArrayList<>();
                    for (aNi ingredient : raw.cvk()) {
                        Map<String, Object> item = new LinkedHashMap<>();
                        item.put("item_id", ingredient.aAi());
                        item.put("quantity", ingredient.bfh());
                        // Preserve this field verbatim until its semantics are proven.
                        item.put("extra_raw", ingredient.cvm());
                        ingredients.add(item);
                    }
                    List<Map<String, Object>> products = new ArrayList<>();
                    for (aNj product : raw.cvl()) {
                        Map<String, Object> item = new LinkedHashMap<>();
                        item.put("item_id", product.aAi());
                        item.put("quantity", product.bfh());
                        products.add(item);
                    }
                    counts[1] += ingredients.size();
                    counts[2] += products.size();
                    row.put("ingredients", ingredients);
                    row.put("products", products);
                    recipes.add(row);
                } catch (Throwable error) {
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("recipe_id", raw.d());
                    entry.put("error_type", error.getClass().getName());
                    entry.put("error", String.valueOf(error.getMessage()));
                    errors.add(entry);
                }
            }
        });

        // Native loader baL maps aKM rows into bFv(id, ckK, ckL, cmM, bBK).
        // baL constructs bFv(id, ckK, ckL, cmM, bBK). bAp.clx() uses ckK
        // to resolve the station-family definition in fyB. bAp.cmG() returns
        // ckL, which cWp.isEnabled() passes to eTo.tW() as the character's
        // profession ID. bAp.GE(recipeId) and bAp.i(recipeId, mode) test cmM.
        apw.bGL().a(new aKM(), new apB<aKM>() {
            @Override
            public void load(aKM raw) {
                definitionCounts[0]++;
                try {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("definition_id", raw.d());
                    row.put("station_family_key", raw.ckK());
                    row.put("profession_id", raw.ckL());
                    row.put("allowed_recipe_ids", raw.cmM());
                    row.put("runtime_bBK_raw", raw.bBK());
                    tableDefinitions.add(row);
                    definitionsById.put(raw.d(), row);
                } catch (RuntimeException error) {
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("definition_id", raw.d());
                    entry.put("error_type", error.getClass().getName());
                    entry.put("error", String.valueOf(error.getMessage()));
                    definitionErrors.add(entry);
                }
            }
        });

        JsonArray mapObjects = JsonParser.parseString(
                Files.readString(Path.of("server/protocol/native-map-objects.json")))
                .getAsJsonArray();
        for (JsonElement element : mapObjects) {
            JsonObject object = element.getAsJsonObject();
            if (!object.get("type").getAsString().equals("CraftTable")) {
                continue;
            }
            long objectId = object.get("id").getAsLong();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("map_id", object.get("map_id").getAsInt());
            row.put("object_id", objectId);
            row.put("x", object.get("x").getAsDouble());
            row.put("y", object.get("y").getAsDouble());
            row.put("z", object.get("z").getAsDouble());
            try {
                bEG nativeObject = bEE.valueOf("CraftTable").bej().bau();
                nativeObject.as(java.util.HexFormat.of().parseHex(
                        object.get("payload_hex").getAsString()));
                String rawParameter = (String) field(nativeObject, "bbz");
                row.put("raw_parameter", rawParameter);
                int definitionId = Integer.parseInt(rawParameter);
                row.put("definition_id", definitionId);
                Map<String, Object> definition = definitionsById.get(definitionId);
                if (definition == null) {
                    row.put("status", "definition_not_found");
                    tableInstanceErrors.add(Map.of(
                            "map_id", row.get("map_id"), "object_id", objectId,
                            "definition_id", definitionId, "error", "No CRAFT_IE_PARAM row"));
                } else {
                    usedDefinitionIds.add(definitionId);
                    row.put("status", "resolved");
                    row.put("profession_id", definition.get("profession_id"));
                    row.put("station_family_key", definition.get("station_family_key"));
                    row.put("allowed_recipe_count", ((int[]) definition.get("allowed_recipe_ids")).length);
                }
            } catch (Exception error) {
                row.put("status", "decode_error");
                row.put("error_type", error.getClass().getName());
                row.put("error", String.valueOf(error.getMessage()));
                tableInstanceErrors.add(row);
            }
            tableInstances.add(row);
        }

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("recipe_records_seen", counts[0]);
        summary.put("recipe_records_exported", recipes.size());
        summary.put("ingredient_records_exported", counts[1]);
        summary.put("product_records_exported", counts[2]);
        summary.put("record_errors", errors.size());
        summary.put("craft_table_definition_records_seen", definitionCounts[0]);
        summary.put("craft_table_definition_records_exported", tableDefinitions.size());
        summary.put("craft_table_definition_errors", definitionErrors.size());
        summary.put("craft_table_instances", tableInstances.size());
        summary.put("craft_table_instance_errors", tableInstanceErrors.size());

        List<Map<String, Object>> unknownAllowedRecipes = new ArrayList<>();
        List<Map<String, Object>> professionMismatches = new ArrayList<>();
        List<Integer> emptyAllowlists = new ArrayList<>();
        int unknownAllowedRecipeCount = 0;
        int professionMismatchCount = 0;
        for (Map<String, Object> definition : tableDefinitions) {
            int definitionId = (int) definition.get("definition_id");
            int professionId = (int) definition.get("profession_id");
            int[] allowed = (int[]) definition.get("allowed_recipe_ids");
            if (allowed.length == 0) {
                emptyAllowlists.add(definitionId);
            }
            for (int recipeId : allowed) {
                Integer recipeProfession = professionByRecipe.get(recipeId);
                if (recipeProfession == null) {
                    unknownAllowedRecipeCount++;
                    if (unknownAllowedRecipes.size() < 100) {
                        unknownAllowedRecipes.add(Map.of(
                                "definition_id", definitionId, "recipe_id", recipeId));
                    }
                } else if (recipeProfession != professionId) {
                    professionMismatchCount++;
                    if (professionMismatches.size() < 100) {
                        professionMismatches.add(Map.of(
                                "definition_id", definitionId,
                                "recipe_id", recipeId,
                                "table_profession_id", professionId,
                                "recipe_profession_id", recipeProfession));
                    }
                }
            }
        }
        List<Integer> unreferencedDefinitions = tableDefinitions.stream()
                .map(row -> (int) row.get("definition_id"))
                .filter(identity -> !usedDefinitionIds.contains(identity))
                .sorted()
                .toList();
        Map<String, Object> definitionValidation = new LinkedHashMap<>();
        definitionValidation.put("table_instances_resolved", tableInstances.size() - tableInstanceErrors.size());
        definitionValidation.put("unique_referenced_definition_ids", usedDefinitionIds.size());
        definitionValidation.put("unreferenced_definition_ids", unreferencedDefinitions);
        definitionValidation.put("empty_allowlist_definition_ids", emptyAllowlists);
        definitionValidation.put("unknown_allowed_recipe_count", unknownAllowedRecipeCount);
        definitionValidation.put("unknown_allowed_recipe_examples", unknownAllowedRecipes);
        definitionValidation.put("profession_mismatch_count", professionMismatchCount);
        definitionValidation.put("profession_mismatch_examples", professionMismatches);

        Map<String, Object> definitionTable = new LinkedHashMap<>();
        definitionTable.put("status", "exported_from_native_reader");
        definitionTable.put("table_id", new aKM().bGI());
        definitionTable.put("table_name", "CRAFT_IE_PARAM");
        definitionTable.put("raw_record", "aKM");
        definitionTable.put("native_reader", "apw");
        definitionTable.put("native_transformer", "baL");
        definitionTable.put("native_runtime_type", "bFv");
        definitionTable.put("field_mapping", Map.of(
                "definition_id", "aKM.d() -> bFv.d() / fly.d()",
                "station_family_key", "aKM.ckK() -> bFv.clx(); bAp.dSw() resolves via fyB.aae()",
                "profession_id", "aKM.ckL() -> bFv.cmG() -> bAp.cmG(); cWp.isEnabled() passes it to eTo.tW()",
                "allowed_recipe_ids", "aKM.cmM() -> bFv.ged(); bAp.GE(recipeId) and bAp.i(recipeId, mode) test membership",
                "runtime_bBK_raw", "aKM.bBK() -> bFv.bBK(); exact domain meaning unresolved"));
        definitionTable.put("note", "CraftTable.bbz is parsed as definition_id and looked up through flz/CRAFT_IE_PARAM. profession_id is ckL/cmG because the enabled check passes it to the character profession model; ckK/clx selects a separate fyA station-family definition. cmM is the recipe allowlist, not a list of blocking restrictions.");

        Map<String, Object> output = new LinkedHashMap<>();
        output.put("source", Map.of(
                "reader", "apw",
                "table_record", "aNh",
                "ingredients_record", "aNi",
                "products_record", "aNj",
                "ingredient_extra", "aNi.cvm() preserved raw; semantics unresolved"));
        output.put("summary", summary);
        output.put("craft_table_definitions", definitionTable);
        output.put("craft_table_definition_validation", definitionValidation);
        output.put("craft_table_definition_rows", tableDefinitions);
        output.put("craft_table_instances", tableInstances);
        output.put("recipes", recipes);
        output.put("errors", errors);
        output.put("craft_table_definition_errors", definitionErrors);
        output.put("craft_table_instance_errors", tableInstanceErrors);

        Path outputPath = Path.of("server/protocol/craft-recipes.json");
        Files.writeString(outputPath, new GsonBuilder().setPrettyPrinting().create().toJson(output));
        System.out.println("recipes_seen=" + counts[0]
                + " recipes_exported=" + recipes.size()
                + " ingredients=" + counts[1]
                + " products=" + counts[2]
                + " errors=" + errors.size()
                + " craft_table_definitions=" + tableDefinitions.size()
                + " craft_table_instances=" + tableInstances.size()
                + " craft_table_instance_errors=" + tableInstanceErrors.size()
                + " output=" + outputPath);
    }

    private static Object field(Object object, String name) throws ReflectiveOperationException {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(object);
            } catch (NoSuchFieldException ignored) {
                // Continue through the native object hierarchy.
            }
        }
        throw new NoSuchFieldException(name);
    }
}
