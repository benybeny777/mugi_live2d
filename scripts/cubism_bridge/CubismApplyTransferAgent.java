package mugi.bridge;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.io.File;
import java.io.FileReader;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;

/** Apply only a planner-approved transfer to a copy of the current Cubism document. */
public final class CubismApplyTransferAgent {
    private record Update(Object form, float[] positions) {}

    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 4) {
            throw new IllegalArgumentException("expected plan|output-cmo3|log|document-title");
        }
        SwingUtilities.invokeLater(() -> apply(args));
    }

    private static void apply(String[] args) {
        Path log = Path.of(args[2]);
        try {
            JSONObject plan;
            try (FileReader reader = new FileReader(args[0], StandardCharsets.UTF_8)) {
                plan = (JSONObject) new JSONParser().parse(reader);
            }
            if (!"mugi-live2d/keyform-transfer-plan@1".equals(plan.get("schema"))) {
                throw new IllegalArgumentException("unsupported plan schema: " + plan.get("schema"));
            }
            if (!"ready".equals(plan.get("status"))) {
                throw new IllegalArgumentException("refusing plan whose status is " + plan.get("status"));
            }

            JTable table = findPartsTable(findFrame(args[3]));
            if (table == null) throw new IllegalStateException("expanded parts table not found");
            Map<String, Object> meshes = new LinkedHashMap<>();
            Object model = null;
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3);
                if (cell == null) continue;
                Object source = field(cell, "a");
                if (!source.getClass().getName().contains("CArtMeshSource")) continue;
                String id = String.valueOf(call(source, "getId"));
                if (meshes.put(id, source) != null) throw new IllegalStateException("duplicate ArtMesh id " + id);
                if (model == null) model = field(source, "_modelSource");
            }
            JSONObject invariants = (JSONObject) plan.get("target_invariants");
            int expectedCount = ((Number) invariants.get("artmesh_count")).intValue();
            if (meshes.size() != expectedCount) {
                throw new IllegalStateException("ArtMesh count changed: " + meshes.size() + " != " + expectedCount);
            }

            List<Update> updates = new ArrayList<>();
            for (Object rawMeshPlan : (JSONArray) plan.get("meshes")) {
                JSONObject meshPlan = (JSONObject) rawMeshPlan;
                String targetId = String.valueOf(meshPlan.get("target"));
                Object mesh = meshes.get(targetId);
                if (mesh == null) throw new IllegalStateException("target mesh missing: " + targetId);
                int expectedVertices = ((Number) meshPlan.get("vertex_count")).intValue();
                int actualVertices = ((float[]) call(mesh, "getUvs")).length / 2;
                if (actualVertices != expectedVertices) {
                    throw new IllegalStateException(targetId + ": vertex count changed");
                }

                Object grid = call(mesh, "getKeyformGridSource");
                Map<String, Object> forms = formsByCoordinate(mesh, grid);
                JSONArray plannedForms = (JSONArray) meshPlan.get("forms");
                if (forms.size() != plannedForms.size()) {
                    throw new IllegalStateException(targetId + ": keyform count changed: "
                            + forms.size() + " != " + plannedForms.size());
                }
                for (Object rawFormPlan : plannedForms) {
                    JSONObject formPlan = (JSONObject) rawFormPlan;
                    if (!"replace".equals(formPlan.get("action"))) {
                        throw new IllegalArgumentException(targetId + ": unsupported action " + formPlan.get("action"));
                    }
                    String key = String.valueOf(formPlan.get("key"));
                    Object form = forms.get(key);
                    if (form == null) throw new IllegalStateException(targetId + ": form missing at " + key);
                    JSONArray vertices = (JSONArray) formPlan.get("vertices");
                    if (vertices.size() != expectedVertices) {
                        throw new IllegalStateException(targetId + ": plan vertex count changed at " + key);
                    }
                    float[] positions = new float[expectedVertices * 2];
                    for (int i = 0; i < vertices.size(); i++) {
                        JSONArray point = (JSONArray) vertices.get(i);
                        positions[i * 2] = ((Number) point.get(0)).floatValue();
                        positions[i * 2 + 1] = ((Number) point.get(1)).floatValue();
                    }
                    updates.add(new Update(form, positions));
                }
            }

            for (Update update : updates) call(update.form(), "setPositions", update.positions());
            call(model, "updateModelInstances");
            Object saved = call(model, "saveModel", new File(args[1]), false);
            if (!(saved instanceof Boolean ok) || !ok) throw new IllegalStateException("saveModel returned " + saved);
            Files.writeString(log, "status=ready\nupdates=" + updates.size() + "\noutput=" + args[1] + "\n",
                    StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try {
                Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8);
            } catch (Exception ignoredWriteFailure) {
                error.printStackTrace();
            }
        }
    }

    private static Map<String, Object> formsByCoordinate(Object mesh, Object grid) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        for (Object entry : iterable(field(grid, "_keyformsOnGrid"))) {
            TreeMap<String, Float> coordinate = new TreeMap<>();
            Object access = field(entry, "accessKey");
            for (Object key : iterable(field(access, "_keyOnParameterList"))) {
                Object binding = call(key, "getBinding");
                coordinate.put(String.valueOf(call(binding, "getParameterId")),
                        ((Number) call(key, "getValue")).floatValue());
            }
            StringBuilder canonical = new StringBuilder();
            for (Map.Entry<String, Float> value : coordinate.entrySet()) {
                if (!canonical.isEmpty()) canonical.append(';');
                canonical.append(value.getKey()).append('=')
                        .append(String.format(Locale.ROOT, "%.6f", value.getValue() + 0.0f));
            }
            Object form = call(mesh, "getKeyForm", field(entry, "keyformGuid"));
            if (result.put(canonical.toString(), form) != null) {
                throw new IllegalStateException("duplicate form coordinate " + canonical);
            }
        }
        return result;
    }

    private static JFrame findFrame(String title) {
        for (Window window : Window.getWindows()) {
            if (window instanceof JFrame frame && frame.isVisible() && frame.getTitle().contains(title)) return frame;
        }
        throw new IllegalStateException("visible Cubism document not found: " + title);
    }

    private static JTable findPartsTable(Component component) {
        if (component instanceof JTable table && component.getClass().getName().contains("CPartsTreeTable")) return table;
        if (component instanceof Container container) for (Component child : container.getComponents()) {
            JTable found = findPartsTable(child);
            if (found != null) return found;
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static List<?> iterable(Object value) {
        if (value instanceof List<?> list) return list;
        List<Object> result = new ArrayList<>();
        for (Object item : (Iterable<Object>) value) result.add(item);
        return result;
    }

    private static Object call(Object value, String name, Object... arguments) throws Exception {
        for (Method method : value.getClass().getMethods()) {
            if (method.getName().equals(name) && method.getParameterCount() == arguments.length) {
                return method.invoke(value, arguments);
            }
        }
        throw new NoSuchMethodException(value.getClass().getName() + "." + name);
    }

    private static Object field(Object value, String name) throws Exception {
        for (Class<?> type = value.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field candidate = type.getDeclaredField(name);
                candidate.setAccessible(true);
                return candidate.get(value);
            } catch (NoSuchFieldException ignored) {
            }
        }
        throw new NoSuchFieldException(value.getClass().getName() + "." + name);
    }
}
