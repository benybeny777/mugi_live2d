package mugi.bridge;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;

/** Read-only Cubism Editor bridge that exports a validated keyform manifest. */
final class CubismManifestAgentV3 {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 6) {
            throw new IllegalArgumentException("expected output|title|role|model-id|width|height");
        }
        SwingUtilities.invokeLater(() -> export(args));
    }

    private static void export(String[] args) {
        Path output = Path.of(args[0]);
        try {
            JFrame frame = findFrame(args[1]);
            JTable table = findPartsTable(frame);
            if (table == null) throw new IllegalStateException("expanded parts table not found");

            List<Object> meshes = new ArrayList<>();
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3);
                if (cell == null) continue;
                Object source = field(cell, "a");
                if (source.getClass().getName().contains("CArtMeshSource")) meshes.add(source);
            }
            if (meshes.isEmpty()) throw new IllegalStateException("no ArtMeshes found; expand all parts first");

            Map<String, String> guidToId = new LinkedHashMap<>();
            for (Object mesh : meshes) {
                guidToId.put(String.valueOf(call(mesh, "getGuid")), String.valueOf(call(mesh, "getId")));
            }

            Map<String, Object> parameters = new LinkedHashMap<>();
            Map<String, Float> keyMinimums = new LinkedHashMap<>();
            Map<String, Float> keyMaximums = new LinkedHashMap<>();
            for (Object mesh : meshes) {
                Object grid = call(mesh, "getKeyformGridSource");
                for (Object binding : iterable(field(grid, "_keyformBindings"))) {
                    Object parameter = call(binding, "getParameter");
                    String parameterId = String.valueOf(call(parameter, "getId"));
                    parameters.putIfAbsent(parameterId, parameter);
                    for (Object rawKey : iterable(call(binding, "getKeys"))) {
                        float key = ((Number) rawKey).floatValue();
                        keyMinimums.merge(parameterId, key, Math::min);
                        keyMaximums.merge(parameterId, key, Math::max);
                    }
                }
            }

            StringBuilder json = new StringBuilder(1 << 20);
            json.append("{\n  \"schema\": \"mugi-live2d/keyform-manifest@1\",\n");
            json.append("  \"model\": {\"id\": ").append(quote(args[3]))
                    .append(", \"role\": ").append(quote(args[2]))
                    .append(", \"canvas\": {\"width\": ").append(Integer.parseInt(args[4]))
                    .append(", \"height\": ").append(Integer.parseInt(args[5])).append("}},\n");
            json.append("  \"parameters\": [\n");
            int index = 0;
            for (Map.Entry<String, Object> entry : parameters.entrySet()) {
                Object parameter = entry.getValue();
                if (index++ > 0) json.append(",\n");
                json.append("    {\"id\": ").append(quote(entry.getKey()))
                        .append(", \"name\": ").append(quote(String.valueOf(call(parameter, "getName"))))
                        .append(", \"minimum\": ").append(Float.toString(Math.min(
                                ((Number) call(parameter, "getMinValue")).floatValue(), keyMinimums.get(entry.getKey()))))
                        .append(", \"maximum\": ").append(Float.toString(Math.max(
                                ((Number) call(parameter, "getMaxValue")).floatValue(), keyMaximums.get(entry.getKey()))))
                        .append(", \"default\": ").append(number(call(parameter, "getDefaultValue"))).append("}");
            }
            json.append("\n  ],\n  \"meshes\": [\n");
            for (int meshIndex = 0; meshIndex < meshes.size(); meshIndex++) {
                if (meshIndex > 0) json.append(",\n");
                appendMesh(json, meshes.get(meshIndex), guidToId);
            }
            json.append("\n  ]\n}\n");
            Files.createDirectories(output.toAbsolutePath().getParent());
            Files.writeString(output, json.toString(), StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try {
                Files.writeString(output, "ERROR " + error + "\n", StandardCharsets.UTF_8);
            } catch (Exception ignoredWriteFailure) {
                error.printStackTrace();
            }
        }
    }

    private static void appendMesh(StringBuilder json, Object mesh, Map<String, String> guidToId)
            throws Exception {
        String id = String.valueOf(call(mesh, "getId"));
        Object grid = call(mesh, "getKeyformGridSource");
        List<?> bindings = iterable(field(grid, "_keyformBindings"));
        List<?> entries = iterable(field(grid, "_keyformsOnGrid"));
        int[] indices = (int[]) call(mesh, "getIndices");
        float[] uvs = (float[]) call(mesh, "getUvs");

        json.append("    {\n      \"id\": ").append(quote(id))
                .append(",\n      \"name\": ").append(quote(id))
                .append(",\n      \"vertex_count\": ").append(uvs.length / 2)
                .append(",\n      \"parameters\": [");
        for (int i = 0; i < bindings.size(); i++) {
            if (i > 0) json.append(", ");
            json.append(quote(String.valueOf(call(bindings.get(i), "getParameterId"))));
        }
        json.append("],\n      \"triangles\": [");
        for (int i = 0; i < indices.length; i += 3) {
            if (i > 0) json.append(", ");
            json.append('[').append(indices[i]).append(',').append(indices[i + 1]).append(',')
                    .append(indices[i + 2]).append(']');
        }
        json.append("],\n      \"uvs\": ");
        appendPoints(json, uvs);

        Object referenceForm = null;
        json.append(",\n      \"forms\": [\n");
        for (int i = 0; i < entries.size(); i++) {
            if (i > 0) json.append(",\n");
            Object entry = entries.get(i);
            Object access = field(entry, "accessKey");
            List<?> keys = iterable(field(access, "_keyOnParameterList"));
            Object form = call(mesh, "getKeyForm", field(entry, "keyformGuid"));
            boolean isReference = true;
            json.append("        {\"coordinate\": {");
            for (int k = 0; k < keys.size(); k++) {
                if (k > 0) json.append(", ");
                Object key = keys.get(k);
                Object binding = call(key, "getBinding");
                Object parameter = call(binding, "getParameter");
                float value = ((Number) call(key, "getValue")).floatValue();
                float defaultValue = ((Number) call(parameter, "getDefaultValue")).floatValue();
                isReference &= Math.abs(value - defaultValue) <= 0.000001f;
                json.append(quote(String.valueOf(call(binding, "getParameterId"))))
                        .append(": ").append(Float.toString(value));
            }
            if (isReference) referenceForm = form;
            json.append("}, \"vertices\": ");
            appendPoints(json, (float[]) call(form, "getPositions"));
            json.append('}');
        }
        if (referenceForm == null) throw new IllegalStateException(id + ": no reference form at defaults");

        json.append("\n      ],\n      \"draw_order\": ").append(number(call(referenceForm, "getDrawOrder")))
                .append(",\n      \"opacity\": ").append(number(call(referenceForm, "getOpacity")))
                .append(",\n      \"clipped_by\": [");
        List<?> clipGuids = iterable(call(mesh, "getClipGuidList"));
        for (int i = 0; i < clipGuids.size(); i++) {
            if (i > 0) json.append(", ");
            String guid = String.valueOf(clipGuids.get(i));
            json.append(quote(guidToId.getOrDefault(guid, "guid:" + guid)));
        }
        json.append("]\n    }");
    }

    private static void appendPoints(StringBuilder json, float[] values) {
        if ((values.length & 1) != 0) throw new IllegalArgumentException("odd point coordinate count");
        json.append('[');
        for (int i = 0; i < values.length; i += 2) {
            if (i > 0) json.append(',');
            json.append('[').append(Float.toString(values[i])).append(',')
                    .append(Float.toString(values[i + 1])).append(']');
        }
        json.append(']');
    }

    private static String number(Object value) {
        return value instanceof Float f ? Float.toString(f) : String.valueOf(value);
    }

    private static String quote(String text) {
        StringBuilder result = new StringBuilder(text.length() + 2).append((char) 34);
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            switch (c) {
                case 34 -> result.append((char) 92).append((char) 34);
                case 92 -> result.append((char) 92).append((char) 92);
                case 8 -> result.append((char) 92).append('b');
                case 12 -> result.append((char) 92).append('f');
                case 10 -> result.append((char) 92).append('n');
                case 13 -> result.append((char) 92).append('r');
                case 9 -> result.append((char) 92).append('t');
                default -> {
                    if (c < 0x20) result.append((char) 92).append(String.format("u%04x", (int) c));
                    else result.append(c);
                }
            }
        }
        return result.append((char) 34).toString();
    }

    private static JFrame findFrame(String title) {
        for (Window window : Window.getWindows()) {
            if (window instanceof JFrame frame && frame.isVisible() && frame.getTitle().contains(title)) {
                return frame;
            }
        }
        throw new IllegalStateException("visible Cubism document not found: " + title);
    }

    private static JTable findPartsTable(Component component) {
        if (component instanceof JTable table && component.getClass().getName().contains("CPartsTreeTable")) return table;
        if (component instanceof Container container) {
            for (Component child : container.getComponents()) {
                JTable found = findPartsTable(child);
                if (found != null) return found;
            }
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
