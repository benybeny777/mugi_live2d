package mugi.bridge;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.io.File;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;

/** Duplicate a parameterized ArtMesh as a larger, lower-draw-order underlay. */
final class CubismDuplicateUnderlayAgentImplV12 {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 8) throw new IllegalArgumentException(
                "expected output|log|title|source-id|new-id|scale|draw-order-offset|right-extent");
        SwingUtilities.invokeLater(() -> apply(args));
    }

    private static void apply(String[] args) {
        Path log = Path.of(args[1]);
        try {
            float scale = Float.parseFloat(args[5]);
            float drawOffset = Float.parseFloat(args[6]);
            float rightExtent = Float.parseFloat(args[7]);
            JTable table = findPartsTable(findFrame(args[2]));
            if (table == null) throw new IllegalStateException("expanded parts table not found");
            Object source = null;
            Object model = null;
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3);
                if (cell == null) continue;
                Object candidate = field(cell, "a");
                if (!candidate.getClass().getName().contains("CArtMeshSource")) continue;
                model = field(candidate, "_modelSource"); break;
            }
            if (model == null) throw new IllegalStateException("model source not found");
            for (Object candidate : iterable(call(model, "getAllArtMeshes")))
                if (args[3].equals(String.valueOf(call(candidate, "getId")))) { source = candidate; break; }
            if (source == null) throw new IllegalStateException("source mesh not found: " + args[3]);
            Object existing = call(model, "getObject", args[4]);
            if (existing != null) call(model, "removeParameterControllableSource", existing);

            Object copyContext = Class.forName("com.live2d.core.a").getConstructor().newInstance();
            Object underlay = call(source, "deepCopy", copyContext);
            Class<?> idClass = Class.forName("com.live2d.cubism.doc.model.id.CDrawableId");
            Class<?> guidClass = Class.forName("com.live2d.type.CDrawableGuid");
            call(underlay, "setId", idClass.getConstructor(String.class).newInstance(args[4]));
            call(underlay, "setGuid", guidClass.getConstructor(UUID.class).newInstance(UUID.randomUUID()));
            Object parent = call(source, "getParent");

            // Reserve atlas pixels (2304,0)-(3328,1024) on the 8192 page.
            // Every vertex samples its solid centre, avoiding all source-hair
            // RGB while keeping the original atlas texture object and index.
            float reservedU = (2304.0f + 512.0f) / 8192.0f;
            float reservedV = 1.0f - 512.0f / 8192.0f;
            float[] underlayUvs = ((float[]) call(underlay, "getUvs")).clone();
            for (int index = 0; index < underlayUvs.length; index += 2) {
                underlayUvs[index] = reservedU; underlayUvs[index + 1] = reservedV;
            }
            call(underlay, "setUvs", underlayUvs);

            // The source texture also contains opaque outer locks. Keep only
            // central head triangles in the underlay so those locks are not
            // rendered twice when the underlay vertices move.
            float[] basePositions = (float[]) call(underlay, "getPositions");
            float baseMinX = Float.POSITIVE_INFINITY, baseMinY = Float.POSITIVE_INFINITY;
            float baseMaxX = Float.NEGATIVE_INFINITY, baseMaxY = Float.NEGATIVE_INFINITY;
            for (int i = 0; i < basePositions.length; i += 2) {
                baseMinX = Math.min(baseMinX, basePositions[i]); baseMaxX = Math.max(baseMaxX, basePositions[i]);
                baseMinY = Math.min(baseMinY, basePositions[i + 1]); baseMaxY = Math.max(baseMaxY, basePositions[i + 1]);
            }
            float baseCenterX = (baseMinX + baseMaxX) * 0.5f, baseCenterY = (baseMinY + baseMaxY) * 0.5f;
            float baseHalfWidth = Math.max(0.000001f, (baseMaxX - baseMinX) * 0.5f);
            float baseHalfHeight = Math.max(0.000001f, (baseMaxY - baseMinY) * 0.5f);
            int[] sourceIndices = (int[]) call(underlay, "getIndices");
            List<Integer> centralIndices = new ArrayList<>();
            for (int offset = 0; offset + 2 < sourceIndices.length; offset += 3) {
                float centroidX = 0, centroidY = 0;
                for (int corner = 0; corner < 3; corner++) {
                    int vertex = sourceIndices[offset + corner];
                    centroidX += basePositions[vertex * 2] / 3.0f;
                    centroidY += basePositions[vertex * 2 + 1] / 3.0f;
                }
                float signedNx = (centroidX - baseCenterX) / baseHalfWidth;
                float ny = Math.abs(centroidY - baseCenterY) / baseHalfHeight;
                if (signedNx >= -0.78f && signedNx <= rightExtent && ny <= 0.86f)
                    for (int corner = 0; corner < 3; corner++)
                    centralIndices.add(sourceIndices[offset + corner]);
            }
            int[] filteredIndices = new int[centralIndices.size()];
            for (int index = 0; index < filteredIndices.length; index++) filteredIndices[index] = centralIndices.get(index);
            call(underlay, "setIndices", filteredIndices);

            Object grid = call(underlay, "getKeyformGridSource");
            int forms = 0;
            for (Object entry : iterable(field(grid, "_keyformsOnGrid"))) {
                Object form = call(underlay, "getKeyForm", field(entry, "keyformGuid"));
                float[] positions = ((float[]) call(form, "getPositions")).clone();
                float minX = Float.POSITIVE_INFINITY, minY = Float.POSITIVE_INFINITY;
                float maxX = Float.NEGATIVE_INFINITY, maxY = Float.NEGATIVE_INFINITY;
                for (int i = 0; i < positions.length; i += 2) {
                    minX = Math.min(minX, positions[i]); maxX = Math.max(maxX, positions[i]);
                    minY = Math.min(minY, positions[i + 1]); maxY = Math.max(maxY, positions[i + 1]);
                }
                float centerX = (minX + maxX) * 0.5f, centerY = (minY + maxY) * 0.5f;
                float halfWidth = Math.max(0.000001f, (maxX - minX) * 0.5f);
                float halfHeight = Math.max(0.000001f, (maxY - minY) * 0.5f);
                for (int i = 0; i < positions.length; i += 2) {
                    float normalized = Math.max(Math.abs(positions[i] - centerX) / halfWidth,
                            Math.abs(positions[i + 1] - centerY) / halfHeight);
                    float edgeWeight = Math.max(0.0f, Math.min(1.0f, (1.0f - normalized) / 0.30f));
                    float localScale = 1.0f + (scale - 1.0f) * edgeWeight;
                    positions[i] = centerX + (positions[i] - centerX) * localScale;
                    positions[i + 1] = centerY + (positions[i + 1] - centerY) * localScale;
                }
                call(form, "setPositions", positions);
                Number drawOrder = (Number) call(form, "getDrawOrder");
                call(form, "setDrawOrder", Math.round(drawOrder.floatValue() + drawOffset));
                forms++;
            }
            int childIndex = ((List<?>) call(parent, "getChildren")).size();
            call(parent, "addChild", underlay, childIndex);
            call(model, "updateModelInstances");
            Object saved = call(model, "saveModel", new File(args[0]), false);
            if (!(saved instanceof Boolean ok) || !ok) throw new IllegalStateException("saveModel returned " + saved);
            Files.writeString(log, "status=ready\nsource=" + args[3] + "\nnew=" + args[4]
                    + "\nscale=" + scale + "\nright_extent=" + rightExtent + "\nforms=" + forms
                    + "\ntriangles=" + filteredIndices.length / 3 + "\natlas_rect=2304,0,1024,1024"
                    + "\noutput=" + args[0] + "\n", StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
        }
    }

    @SuppressWarnings("unchecked")
    private static List<?> iterable(Object value) {
        if (value instanceof List<?> list) return list;
        List<Object> result = new ArrayList<>();
        for (Object item : (Iterable<Object>) value) result.add(item);
        return result;
    }
    private static JFrame findFrame(String title) {
        for (Window window : Window.getWindows()) if (window instanceof JFrame frame
                && frame.isVisible() && frame.getTitle().contains(title)) return frame;
        throw new IllegalStateException("visible Cubism document not found: " + title);
    }
    private static JTable findPartsTable(Component component) {
        if (component instanceof JTable table && component.getClass().getName().contains("CPartsTreeTable")) return table;
        if (component instanceof Container container) for (Component child : container.getComponents()) {
            JTable found = findPartsTable(child); if (found != null) return found;
        }
        return null;
    }
    private static Object call(Object value, String name, Object... arguments) throws Exception {
        for (Method method : value.getClass().getMethods()) if (method.getName().equals(name)
                && method.getParameterCount() == arguments.length) {
            try { return method.invoke(value, arguments); } catch (IllegalArgumentException ignored) { }
        }
        throw new NoSuchMethodException(value.getClass().getName() + "." + name + "/" + arguments.length);
    }
    private static Object field(Object value, String name) throws Exception {
        for (Class<?> type = value.getClass(); type != null; type = type.getSuperclass()) try {
            Field candidate = type.getDeclaredField(name); candidate.setAccessible(true); return candidate.get(value);
        } catch (NoSuchFieldException ignored) { }
        throw new NoSuchFieldException(value.getClass().getName() + "." + name);
    }
}
