package mugi.bridge;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.swing.AbstractButton;
import javax.swing.JFrame;
import javax.swing.JMenu;
import javax.swing.JMenuBar;
import javax.swing.SwingUtilities;

/** Read-only dump of Cubism's menu hierarchy and bound action classes. */
public final class CubismMenuDumpAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        SwingUtilities.invokeLater(() -> dump(args));
    }
    private static void dump(String[] args) {
        try {
            JFrame frame = null;
            for (Window window : Window.getWindows()) if (window instanceof JFrame candidate
                    && candidate.isVisible() && candidate.getTitle().contains(args[1])) { frame = candidate; break; }
            if (frame == null) throw new IllegalStateException("window not found");
            StringBuilder out = new StringBuilder();
            JMenuBar bar = frame.getJMenuBar();
            for (int index = 0; index < bar.getMenuCount(); index++) append(out, bar.getMenu(index), "");
            Files.writeString(Path.of(args[0]), out.toString(), StandardCharsets.UTF_8);
        } catch (Throwable error) { error.printStackTrace(); }
    }
    private static void append(StringBuilder out, Component component, String prefix) {
        String label = component instanceof AbstractButton button ? button.getText() : component.getClass().getSimpleName();
        String action = component instanceof AbstractButton button && button.getAction() != null
                ? button.getAction().getClass().getName() : "";
        StringBuilder listeners = new StringBuilder();
        if (component instanceof AbstractButton button) for (var listener : button.getActionListeners()) {
            if (!listeners.isEmpty()) listeners.append(','); listeners.append(listener.getClass().getName());
        }
        out.append(prefix).append(label).append('\t').append(component.getClass().getName()).append('\t')
                .append(action).append('\t').append(component.isEnabled()).append('\t').append(listeners).append('\n');
        if (component instanceof JMenu menu) for (Component child : menu.getMenuComponents()) append(out, child, prefix + "  ");
        else if (component instanceof Container container) for (Component child : container.getComponents()) append(out, child, prefix + "  ");
    }
}
