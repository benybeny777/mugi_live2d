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
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;

/** Assign an existing semantic underlay to a reserved atlas pixel. */
public final class CubismReservedUvAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        SwingUtilities.invokeLater(() -> apply(args));
    }
    private static void apply(String[] args) {
        Path log = Path.of(args[1]);
        try {
            JTable table = findPartsTable(findFrame(args[2]));
            Object model = null;
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3); if (cell == null) continue;
                Object source = field(cell, "a");
                if (source.getClass().getName().contains("CArtMeshSource")) { model = field(source, "_modelSource"); break; }
            }
            if (model == null) throw new IllegalStateException("model source not found");
            Object underlay = null;
            for (Object mesh : iterable(call(model, "getAllArtMeshes")))
                if (args[3].equals(String.valueOf(call(mesh, "getId")))) { underlay = mesh; break; }
            if (underlay == null) throw new IllegalStateException("underlay not found: " + args[3]);
            float[] uvs = ((float[]) call(underlay, "getUvs")).clone();
            float u = (2304.0f + 512.0f) / 8192.0f, v = 1.0f - 512.0f / 8192.0f;
            for (int index = 0; index < uvs.length; index += 2) { uvs[index] = u; uvs[index + 1] = v; }
            call(underlay, "setUvs", uvs);
            call(model, "updateModelInstances");
            Object saved = call(model, "saveModel", new File(args[0]), false);
            if (!(saved instanceof Boolean ok) || !ok) throw new IllegalStateException("saveModel returned " + saved);
            Files.writeString(log, "status=ready\nmesh=" + args[3] + "\nvertices=" + uvs.length / 2
                    + "\natlas_rect=2304,0,1024,1024\noutput=" + args[0] + "\n", StandardCharsets.UTF_8);
        } catch (Throwable error) {
            Throwable cause = error.getCause() != null ? error.getCause() : error;
            try { Files.writeString(log, "status=error\nerror=" + cause + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { cause.printStackTrace(); }
        }
    }
    @SuppressWarnings("unchecked") private static List<?> iterable(Object value) {
        if (value instanceof List<?> list) return list; List<Object> result = new ArrayList<>();
        for (Object item : (Iterable<Object>) value) result.add(item); return result;
    }
    private static JFrame findFrame(String title) { for (Window window : Window.getWindows())
        if (window instanceof JFrame frame && frame.isVisible() && frame.getTitle().contains(title)) return frame;
        throw new IllegalStateException("window not found: " + title); }
    private static JTable findPartsTable(Component component) { if (component instanceof JTable table
        && component.getClass().getName().contains("CPartsTreeTable")) return table;
        if (component instanceof Container container) for (Component child : container.getComponents()) {
            JTable found = findPartsTable(child); if (found != null) return found; } return null; }
    private static Object call(Object value, String name, Object... arguments) throws Exception {
        for (Method method : value.getClass().getMethods()) if (method.getName().equals(name)
                && method.getParameterCount() == arguments.length) try { return method.invoke(value, arguments); }
                catch (IllegalArgumentException ignored) { }
        throw new NoSuchMethodException(value.getClass().getName() + "." + name); }
    private static Object field(Object value, String name) throws Exception { for (Class<?> type=value.getClass();type!=null;type=type.getSuperclass()) try {
        Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(value);}catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(value.getClass().getName()+"."+name); }
}
