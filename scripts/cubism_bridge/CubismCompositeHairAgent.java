package mugi.bridge;

import com.live2d.cubism.CEAppCtrl;
import com.live2d.cubism.doc.model.CModelSource;
import com.live2d.cubism.doc.model.drawable.artMesh.CArtMeshSource;
import com.live2d.cubism.doc.modeling.CModelingDocument;
import java.io.File;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import javax.swing.SwingUtilities;

/** Add one transparent hair-composite quad driven by the back-hair keyforms. */
public final class CubismCompositeHairAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 11) throw new IllegalArgumentException(
                "expected output|log|title|u-left|u-right|v-top|v-bottom|x0|y0|x1|y1");
        SwingUtilities.invokeLater(() -> apply(args));
    }

    private static void apply(String[] args) {
        Path log = Path.of(args[1]);
        try {
            float uLeft = Float.parseFloat(args[3]);
            float uRight = Float.parseFloat(args[4]);
            float vTop = Float.parseFloat(args[5]);
            float vBottom = Float.parseFloat(args[6]);
            float x0 = Float.parseFloat(args[7]);
            float y0 = Float.parseFloat(args[8]);
            float x1 = Float.parseFloat(args[9]);
            float y1 = Float.parseFloat(args[10]);
            File output = new File(args[0]);
            if (output.exists()) throw new IllegalStateException("refusing to overwrite output: " + output);
            CEAppCtrl app = CEAppCtrl.Companion.b();
            CModelingDocument document = findDocument(app, args[2]);
            File openModel = document.getFile();
            String tempSegment = File.separator + "temp" + File.separator;
            if (openModel == null
                    || !openModel.getCanonicalPath().toLowerCase(Locale.ROOT).contains(tempSegment)) {
                throw new IllegalStateException("refusing to modify a non-temp Cubism document: " + openModel);
            }
            CModelSource model = document.getModelSource();
            CArtMeshSource source = null;
            for (CArtMeshSource mesh : model.getAllArtMeshes()) {
                if ("ArtMesh47".equals(String.valueOf(mesh.getId()))) source = mesh;
            }
            if (source == null) throw new IllegalStateException("ArtMesh47 not found");
            if (model.getObject("ArtMeshHairCompositeFill") != null) {
                throw new IllegalStateException("ArtMeshHairCompositeFill already exists");
            }
            int before = model.getAllArtMeshes().size();

            Object context = Class.forName("com.live2d.core.a").getConstructor().newInstance();
            CArtMeshSource fill = (CArtMeshSource) source.deepCopy((com.live2d.core.a) context);
            Class<?> idClass = Class.forName("com.live2d.cubism.doc.model.id.CDrawableId");
            Class<?> guidClass = Class.forName("com.live2d.type.CDrawableGuid");
            fill.setId((com.live2d.cubism.doc.model.id.CDrawableId)
                    idClass.getConstructor(String.class).newInstance("ArtMeshHairCompositeFill"));
            fill.setGuid((com.live2d.type.CDrawableGuid)
                    guidClass.getConstructor(UUID.class).newInstance(UUID.randomUUID()));
            fill.setUvs(new float[] {uRight, vTop, uLeft, vTop, uRight, vBottom, uLeft, vBottom});
            fill.setIndices(new int[] {1, 0, 2, 2, 3, 1});

            Object grid = call(fill, "getKeyformGridSource");
            float[] reference = null;
            int forms = 0;
            for (Object entry : iterable(field(grid, "_keyformsOnGrid"))) {
                Object form = call(fill, "getKeyForm", field(entry, "keyformGuid"));
                float[] old = ((float[]) call(form, "getPositions")).clone();
                float minX = Float.POSITIVE_INFINITY, minY = Float.POSITIVE_INFINITY;
                float maxX = Float.NEGATIVE_INFINITY, maxY = Float.NEGATIVE_INFINITY;
                for (int i = 0; i < old.length; i += 2) {
                    minX = Math.min(minX, old[i]); maxX = Math.max(maxX, old[i]);
                    minY = Math.min(minY, old[i + 1]); maxY = Math.max(maxY, old[i + 1]);
                }
                maxY += (maxY - minY) * 0.14f;
                float[] quad = {maxX, maxY, minX, maxY, maxX, minY, minX, minY};
                call(form, "setPositions", quad);
                call(form, "setDrawOrder", 798);
                if (reference == null) reference = quad;
                forms++;
            }
            if (reference == null) throw new IllegalStateException("no keyforms");
            fill.setPositions(reference);
            Object parent = source.getParent();
            int childIndex = ((List<?>) call(parent, "getChildren")).size();
            call(parent, "addChild", fill, childIndex);
            model.updateModelInstances();
            if (model.getAllArtMeshes().size() != before + 1) throw new IllegalStateException(
                    "expected " + (before + 1) + " ArtMeshes, found " + model.getAllArtMeshes().size());
            output.getParentFile().mkdirs();
            if (!model.saveModel(output, false)) throw new IllegalStateException("saveModel failed: " + output);
            String result = "status=ready\nforms=" + forms + "\nartmeshes=" + (before + 1) + "\nparameters="
                    + model.getAllParameters().size() + "\noutput=" + output.getCanonicalPath() + "\n";
            Files.writeString(log, result, StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
        }
    }

    private static CModelingDocument findDocument(CEAppCtrl app, String title) {
        for (CModelingDocument document : app.getAllModelDocs()) {
            File file = document.getFile();
            if ((file != null && file.getName().contains(title)) || document.getFileName().contains(title)) return document;
        }
        throw new IllegalStateException("document not found: " + title);
    }

    private static Object field(Object target, String name) throws Exception {
        for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) try {
            Field value = type.getDeclaredField(name); value.setAccessible(true); return value.get(target);
        } catch (NoSuchFieldException ignored) { }
        throw new NoSuchFieldException(target.getClass().getName() + "." + name);
    }

    private static Object call(Object target, String name, Object... args) throws Exception {
        for (Method method : target.getClass().getMethods()) {
            if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
            try { return method.invoke(target, args); } catch (IllegalArgumentException ignored) { }
        }
        throw new NoSuchMethodException(target.getClass().getName() + "." + name + "/" + args.length);
    }

    private static List<?> iterable(Object value) {
        if (value instanceof List<?> list) return list;
        List<Object> result = new ArrayList<>();
        for (Object item : (Iterable<?>) value) result.add(item);
        return result;
    }
}
