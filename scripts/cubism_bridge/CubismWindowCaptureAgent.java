package mugi.bridge;

import java.awt.Rectangle;
import java.awt.Robot;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.nio.file.Path;
import javax.imageio.ImageIO;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

/** Capture a Cubism document window from Cubism's interactive AWT session. */
public final class CubismWindowCaptureAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        SwingUtilities.invokeLater(() -> {
            try {
                JFrame frame = null;
                for (Window window : Window.getWindows()) if (window instanceof JFrame candidate
                        && candidate.isVisible() && candidate.getTitle().contains(args[1])) { frame = candidate; break; }
                if (frame == null) throw new IllegalStateException("window not found: " + args[1]);
                frame.toFront();
                ImageIO.write(new Robot().createScreenCapture(new Rectangle(frame.getLocationOnScreen(), frame.getSize())),
                        "png", Path.of(args[0]).toFile());
            } catch (Throwable error) { error.printStackTrace(); }
        });
    }
}
