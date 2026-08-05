package mugi.bridge;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Constructor;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;

/** Read-only reflection probe for one Cubism ArtMesh and its model source. */
public final class CubismReflectionAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 4) throw new IllegalArgumentException("expected output|title|mesh-id|mode");
        SwingUtilities.invokeLater(() -> inspect(args));
    }

    private static void inspect(String[] args) {
        Path output = Path.of(args[0]);
        try {
            JTable table = findPartsTable(findFrame(args[1]));
            if (table == null) throw new IllegalStateException("expanded parts table not found");
            Object mesh = null;
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3);
                if (cell == null) continue;
                Object candidate = field(cell, "a");
                if (!candidate.getClass().getName().contains("CArtMeshSource")) continue;
                if (args[2].equals(String.valueOf(call(candidate, "getId")))) { mesh = candidate; break; }
            }
            if (mesh == null) throw new IllegalStateException("mesh not found: " + args[2]);
            Object model = field(mesh, "_modelSource");
            StringBuilder text = new StringBuilder();
            appendType(text, "mesh", mesh.getClass());
            appendType(text, "model", model.getClass());
            appendType(text, "copy-context", Class.forName("com.live2d.core.a"));
            appendType(text, "drawable-id", Class.forName("com.live2d.cubism.doc.model.id.CDrawableId"));
            appendType(text, "drawable-guid", Class.forName("com.live2d.type.CDrawableGuid"));
            appendType(text, "mesh-texture", call(mesh, "getTexture").getClass());
            appendType(text, "texture-list", call(call(model, "getTextureManager"), "getTextureList").getClass());
            Files.writeString(output, text.toString(), StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(output, "ERROR " + error + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
        }
    }

    private static void appendType(StringBuilder out, String label, Class<?> type) {
        out.append("[" + label + "] " + type.getName() + "\n");
        out.append("constructors\n");
        Arrays.stream(type.getDeclaredConstructors()).map(Constructor::toGenericString).sorted()
                .forEach(value -> out.append(value).append('\n'));
        for (Class<?> current = type; current != null; current = current.getSuperclass()) {
            out.append("class " + current.getName() + "\nfields\n");
            Arrays.stream(current.getDeclaredFields()).map(Field::toGenericString).sorted()
                    .forEach(value -> out.append(value).append('\n'));
            out.append("methods\n");
            Arrays.stream(current.getDeclaredMethods()).map(Method::toGenericString).sorted()
                    .forEach(value -> out.append(value).append('\n'));
        }
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
                && method.getParameterCount() == arguments.length) return method.invoke(value, arguments);
        throw new NoSuchMethodException(value.getClass().getName() + "." + name);
    }

    private static Object field(Object value, String name) throws Exception {
        for (Class<?> type = value.getClass(); type != null; type = type.getSuperclass()) try {
            Field candidate = type.getDeclaredField(name); candidate.setAccessible(true); return candidate.get(value);
        } catch (NoSuchFieldException ignored) { }
        throw new NoSuchFieldException(value.getClass().getName() + "." + name);
    }
}
