package mugi.bridge;

import com.live2d.cubism.doc.model.CModelSource;
import com.live2d.cubism.doc.model.exporter.CMocExportFormat;
import com.live2d.cubism.doc.model.exporter.CMocExportSetting;
import com.live2d.cubism.doc.model.exporter.dD;
import com.live2d.cubism.doc.model.exporter.w;
import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.File;
import java.util.List;
import javax.swing.JFrame;
import javax.swing.JTable;
import javax.swing.SwingUtilities;

/** Reproducible MOC exporter using Cubism's bundled exporter implementation.
 *
 * The MOC is written before its textures, so the presence of the MOC alone does
 * not mean the export finished. A completion marker is written last, and only
 * after every texture has been written, so a caller can wait for that instead.
 */
final class CubismMocExportAgentImplV4 {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 3) throw new IllegalArgumentException("expected output|title|sdk");
        SwingUtilities.invokeLater(() -> export(args));
    }

    private static void export(String[] args) {
        try {
            JTable table = findPartsTable(findFrame(args[1]));
            if (table == null) throw new IllegalStateException("expanded parts table not found");
            CModelSource model = null;
            for (int row = 0; row < table.getRowCount(); row++) {
                Object cell = table.getValueAt(row, 3);
                if (cell == null) continue;
                Object source = field(cell, "a");
                if (source.getClass().getName().contains("CArtMeshSource")) {
                    model = (CModelSource) field(source, "_modelSource"); break;
                }
            }
            if (model == null) throw new IllegalStateException("model source not found");
            CMocExportSetting setting = new CMocExportSetting();
            setting.setExportFormat("sdk4".equals(args[2]) ? CMocExportFormat.V4_02_00 : CMocExportFormat.V5_03_00);
            int canvasWidth = model.getCanvas().getPixelWidth();
            int canvasHeight = model.getCanvas().getPixelHeight();
            setting.setPixelsPerUnit(canvasWidth);
            setting.setOriginX(canvasWidth * 0.5f);
            setting.setOriginY(canvasHeight * 0.5f);
            setting.setEnableExtendEdgeColor(false);
            w exporter = new w();
            exporter.a(setting);
            Class<?> progressClass = Class.forName("com.live2d.util.a.a");
            Object progress = progressClass.getMethod("e").invoke(null);
            Method exportMethod = w.class.getMethod("a", CModelSource.class, progressClass);
            dD result = (dD) exportMethod.invoke(exporter, model, progress);
            List<Byte> boxed = result.a();
            byte[] bytes = new byte[boxed.size()];
            for (int index = 0; index < boxed.size(); index++) bytes[index] = boxed.get(index);
            Files.write(Path.of(args[0]), bytes);
            StringBuilder written = new StringBuilder("moc_bytes=").append(bytes.length).append('\n');
            for (int index = 0; index < result.b().size(); index++) {
                File texture = new File(args[0] + ".texture_" + index + ".png");
                result.b().get(index).getImage().writeImage(texture);
                if (!texture.isFile() || texture.length() == 0) {
                    throw new IllegalStateException("texture not written: " + texture);
                }
                written.append("texture_").append(index).append('=').append(texture.length()).append('\n');
            }
            written.append("textures=").append(result.b().size()).append('\n');
            // Written last so a caller can treat this file as "export complete".
            Files.writeString(Path.of(args[0] + ".done.txt"), written.toString(), StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(Path.of(args[0] + ".error.txt"), error.toString()); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
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
    private static Object field(Object value, String name) throws Exception {
        for (Class<?> type = value.getClass(); type != null; type = type.getSuperclass()) try {
            Field candidate = type.getDeclaredField(name); candidate.setAccessible(true); return candidate.get(value);
        } catch (NoSuchFieldException ignored) { }
        throw new NoSuchFieldException(value.getClass().getName() + "." + name);
    }
}
