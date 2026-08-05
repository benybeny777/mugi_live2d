package mugi.bridge;

import com.live2d.cubism.CEAppCtrl;
import com.live2d.cubism.doc.model.CModel;
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
import java.util.List;
import javax.swing.SwingUtilities;

/** Set every keyform draw order for one temporary ArtMesh. */
public final class CubismDrawOrderAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 7) throw new IllegalArgumentException(
                "expected output|log|title|mesh|draw-order|expected-count|note");
        SwingUtilities.invokeLater(() -> apply(args));
    }

    private static void apply(String[] args) {
        Path log = Path.of(args[1]);
        try {
            CModelingDocument document = null;
            for (CModelingDocument candidate : CEAppCtrl.Companion.b().getAllModelDocs()) {
                File file = candidate.getFile();
                if ((file != null && file.getName().contains(args[2]))
                        || candidate.getFileName().contains(args[2])) document = candidate;
            }
            if (document == null) throw new IllegalStateException("document not found: " + args[2]);
            CModelSource model = document.getModelSource();
            CArtMeshSource mesh = null;
            for (CArtMeshSource candidate : model.getAllArtMeshes()) {
                if (args[3].equals(String.valueOf(candidate.getId()))) mesh = candidate;
            }
            if (mesh == null) throw new IllegalStateException("mesh not found: " + args[3]);
            int expected = Integer.parseInt(args[5]);
            if (model.getAllArtMeshes().size() != expected) throw new IllegalStateException(
                    "ArtMesh count changed: " + model.getAllArtMeshes().size() + " != " + expected);
            int drawOrder = Integer.parseInt(args[4]);
            Object grid = call(mesh, "getKeyformGridSource");
            int forms = 0;
            for (Object entry : iterable(field(grid, "_keyformsOnGrid"))) {
                Object form = call(mesh, "getKeyForm", field(entry, "keyformGuid"));
                call(form, "setDrawOrder", drawOrder);
                forms++;
            }
            mesh.setMeshUpdatedFlag__testImpl();
            model.updateModelInstances();
            for (CModel instance : model.getModelInstances()) instance.reinitModelInstance();
            File output = new File(args[0]);
            output.getParentFile().mkdirs();
            if (!model.saveModel(output, false)) throw new IllegalStateException("saveModel failed: " + output);
            Files.writeString(log, "status=ready\nmesh=" + args[3] + "\ndraw_order=" + drawOrder
                    + "\nforms=" + forms + "\nartmeshes=" + expected + "\noutput="
                    + output.getCanonicalPath() + "\nnote=" + args[6] + "\n", StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
        }
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
        java.util.ArrayList<Object> result = new java.util.ArrayList<>();
        for (Object item : (Iterable<?>) value) result.add(item);
        return result;
    }
}
