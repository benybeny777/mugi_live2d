package mugi.bridge;

import com.live2d.cubism.CEAppCtrl;
import com.live2d.cubism.doc.model.CModelSource;
import com.live2d.cubism.doc.model.texture.LayeredImageWrapper;
import com.live2d.cubism.doc.modeling.CModelingDocument;
import com.live2d.cubism.doc.resources.CLayeredImage;
import com.live2d.graphics.psd.CPsdDocument;
import java.io.File;
import java.lang.instrument.Instrumentation;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import javax.swing.SwingUtilities;
import javax.swing.Timer;

/** Re-import one PSD into a disposable copy of an open Cubism model.
 *
 * The caller opens a copied CMO3, never the master.  The agent uses Cubism's
 * own PSD similarity/replacement process and saves only when the rig topology
 * (ArtMesh and parameter counts) stays unchanged.
 */
public final class CubismPsdReimportAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 4) {
            throw new IllegalArgumentException("expected psd|output-cmo3|log|document-title");
        }
        SwingUtilities.invokeLater(() -> reimport(args));
    }

    private static void reimport(String[] args) {
        Path log = Path.of(args[2]);
        try {
            File psd = new File(args[0]);
            File output = new File(args[1]);
            if (!psd.isFile()) throw new IllegalArgumentException("PSD not found: " + psd);
            CEAppCtrl app = CEAppCtrl.Companion.b();
            if (app == null) throw new IllegalStateException("Cubism application controller not ready");
            CModelingDocument document = findDocument(app, args[3]);
            File openModel = document.getFile();
            String tempSegment = File.separator + "temp" + File.separator;
            if (openModel == null
                    || !openModel.getCanonicalPath().toLowerCase(Locale.ROOT).contains(tempSegment)) {
                throw new IllegalStateException("refusing to modify a non-temp Cubism document: " + openModel);
            }
            if (output.exists()) throw new IllegalStateException("refusing to overwrite output: " + output);
            CModelSource model = document.getModelSource();
            int artMeshesBefore = model.getAllArtMeshes().size();
            int parametersBefore = model.getAllParameters().size();

            CPsdDocument parsed = CPsdDocument.a.a(psd, true, true);
            if (parsed == null) throw new IllegalStateException("Cubism rejected PSD: " + psd);
            CLayeredImage replacement = new CLayeredImage(parsed, psd, psd.getName());
            List<LayeredImageWrapper> wrappers = model.getTextureManager().getReplaceableRawImages();
            if (wrappers.isEmpty()) wrappers = model.getTextureManager().getRawImages();
            List<CLayeredImage> previous = new ArrayList<>();
            for (LayeredImageWrapper wrapper : wrappers) previous.add(wrapper.getImage());
            if (previous.isEmpty()) throw new IllegalStateException("model has no replaceable PSD resources");

            com.live2d.cubism.process.psd.a.a.a(app, replacement, psd, document, previous);
            Timer settle = new Timer(5000, event -> verifyAndSave(
                    log,
                    psd,
                    output,
                    model,
                    replacement,
                    previous.size(),
                    artMeshesBefore,
                    parametersBefore));
            settle.setRepeats(false);
            settle.start();
        } catch (Throwable error) {
            writeError(log, error);
        }
    }

    private static void verifyAndSave(
            Path log,
            File psd,
            File output,
            CModelSource model,
            CLayeredImage replacement,
            int previousCount,
            int artMeshesBefore,
            int parametersBefore) {
        try {
            model.updateModelInstances();
            int artMeshesAfter = model.getAllArtMeshes().size();
            int parametersAfter = model.getAllParameters().size();
            if (artMeshesAfter != artMeshesBefore) {
                throw new IllegalStateException(
                        "ArtMesh count changed: " + artMeshesBefore + " -> " + artMeshesAfter);
            }
            if (parametersAfter != parametersBefore) {
                throw new IllegalStateException(
                        "parameter count changed: " + parametersBefore + " -> " + parametersAfter);
            }
            output.getParentFile().mkdirs();
            if (!model.saveModel(output, false)) {
                throw new IllegalStateException("saveModel returned false: " + output);
            }
            String result = "status=ready\n"
                    + "psd=" + psd.getCanonicalPath() + "\n"
                    + "previous_psds=" + previousCount + "\n"
                    + "replacement_layers=" + replacement.getChildren().size() + "\n"
                    + "artmeshes=" + artMeshesAfter + "\n"
                    + "parameters=" + parametersAfter + "\n"
                    + "output=" + output.getCanonicalPath() + "\n";
            Files.writeString(log, result, StandardCharsets.UTF_8);
        } catch (Throwable error) {
            writeError(log, error);
        }
    }

    private static void writeError(Path log, Throwable error) {
        try {
            Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8);
        } catch (Exception ignoredWriteFailure) {
            error.printStackTrace();
        }
    }

    private static CModelingDocument findDocument(CEAppCtrl app, String title) {
        for (CModelingDocument document : app.getAllModelDocs()) {
            File file = document.getFile();
            if ((file != null && file.getName().contains(title))
                    || document.getFileName().contains(title)) return document;
        }
        throw new IllegalStateException("open Cubism document not found: " + title);
    }
}
