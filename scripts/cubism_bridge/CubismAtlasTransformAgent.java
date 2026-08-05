package mugi.bridge;

import com.live2d.cubism.CEAppCtrl;
import com.live2d.cubism.doc.model.CModelSource;
import com.live2d.cubism.doc.model.CModel;
import com.live2d.cubism.doc.model.drawable.TextureState;
import com.live2d.cubism.doc.model.drawable.artMesh.CArtMeshSource;
import com.live2d.cubism.doc.model.extension.textureInput.CTextureInputExtension;
import com.live2d.cubism.doc.model.extension.textureInput.CTextureInput_TextureAtlasRegion;
import com.live2d.cubism.doc.modeling.CModelingDocument;
import com.live2d.type.CAffine;
import java.io.File;
import java.lang.instrument.Instrumentation;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.swing.SwingUtilities;

/** Give a generated quad the same atlas transform as a known-good mesh. */
public final class CubismAtlasTransformAgent {
    public static void agentmain(String argument, Instrumentation ignored) {
        String[] args = argument.split("\\|", -1);
        if (args.length != 11) throw new IllegalArgumentException(
                "expected output|log|title|target|donor|left|right|top|bottom|expected-count|note");
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
            CArtMeshSource target = null, donor = null;
            for (CArtMeshSource mesh : model.getAllArtMeshes()) {
                if (args[3].equals(String.valueOf(mesh.getId()))) target = mesh;
                if (args[4].equals(String.valueOf(mesh.getId()))) donor = mesh;
            }
            if (target == null || donor == null) throw new IllegalStateException("target or donor mesh not found");
            if (target.getUvs().length != 8) throw new IllegalStateException("target is not a four-vertex mesh");
            int expected = Integer.parseInt(args[9]);
            if (model.getAllArtMeshes().size() != expected) throw new IllegalStateException(
                    "ArtMesh count changed: " + model.getAllArtMeshes().size() + " != " + expected);

            CTextureInputExtension targetExtension = target.getTextureInputExtension();
            CTextureInputExtension donorExtension = donor.getTextureInputExtension();
            CTextureInput_TextureAtlasRegion targetAtlas = targetExtension.getTextureAtlasInput();
            CTextureInput_TextureAtlasRegion donorAtlas = donorExtension.getTextureAtlasInput();
            if (targetAtlas == null || donorAtlas == null) throw new IllegalStateException("atlas input missing");
            String targetBefore = java.util.Arrays.toString(
                    ((CAffine) targetAtlas.getAtlasLocalToCanvasTransform()).getMatrix());
            String donorMatrix = java.util.Arrays.toString(
                    ((CAffine) donorAtlas.getAtlasLocalToCanvasTransform()).getMatrix());
            targetAtlas.setTextureAtlasGuid(donorAtlas.getTextureAtlasGuid());
            float left = Float.parseFloat(args[5]), right = Float.parseFloat(args[6]);
            float top = Float.parseFloat(args[7]), bottom = Float.parseFloat(args[8]);
            int atlasWidth = donorAtlas.getTextureAtlas().getWidth();
            int atlasHeight = donorAtlas.getTextureAtlas().getHeight();
            float atlasLeft = left * atlasWidth;
            float atlasRight = right * atlasWidth;
            float atlasTop = (1.0f - top) * atlasHeight;
            float atlasBottom = (1.0f - bottom) * atlasHeight;
            float[] positions = target.getPositions();
            float minX = Float.POSITIVE_INFINITY, maxX = Float.NEGATIVE_INFINITY;
            float minY = Float.POSITIVE_INFINITY, maxY = Float.NEGATIVE_INFINITY;
            for (int index = 0; index < positions.length; index += 2) {
                minX = Math.min(minX, positions[index]);
                maxX = Math.max(maxX, positions[index]);
                minY = Math.min(minY, positions[index + 1]);
                maxY = Math.max(maxY, positions[index + 1]);
            }
            double scaleX = (maxX - minX) / (atlasRight - atlasLeft);
            // Cubism's MOC UV convention has texture V increasing upward, so
            // the atlas-local Y axis must be inverted against canvas Y.
            double scaleY = (minY - maxY) / (atlasBottom - atlasTop);
            double translateX = minX - scaleX * atlasLeft;
            double translateY = maxY - scaleY * atlasTop;
            CAffine reservedTransform = new CAffine();
            reservedTransform.setTransform(scaleX, 0.0, 0.0, scaleY, translateX, translateY);
            targetAtlas.setAtlasLocalToCanvasTransform(reservedTransform);
            targetExtension.setCurrentTextureInputData(targetAtlas);
            target.setTexture(donor.getTexture());
            target.setTextureState(TextureState.TEXTURE_ATLAS);
            // Match the same conversion that the MOC exporter performs after
            // cloning the document, so both the source and export agree.
            targetExtension.updateArtMeshSourceUvs();
            target.setMeshUpdatedFlag__testImpl();
            model.updateModelInstances();
            for (CModel instance : model.getModelInstances()) instance.reinitModelInstance();

            File output = new File(args[0]);
            output.getParentFile().mkdirs();
            if (!model.saveModel(output, false)) throw new IllegalStateException("saveModel failed: " + output);
            Files.writeString(log, "status=ready\ntarget=" + args[3] + "\ndonor=" + args[4]
                    + "\nartmeshes=" + expected + "\noutput=" + output.getCanonicalPath()
                    + "\ntarget_before=" + targetBefore + "\ndonor_matrix=" + donorMatrix
                    + "\ntarget_after=" + java.util.Arrays.toString(
                            ((CAffine) targetAtlas.getAtlasLocalToCanvasTransform()).getMatrix())
                    + "\npositions=" + java.util.Arrays.toString(positions)
                    + "\nuvs_after=" + java.util.Arrays.toString(target.getUvs())
                    + "\natlas=" + atlasWidth + "x" + atlasHeight
                    + "\ncurrent=" + targetExtension.getCurrentTextureInputData().getClass().getName()
                    + "\nnote=" + args[10] + "\n", StandardCharsets.UTF_8);
        } catch (Throwable error) {
            try { Files.writeString(log, "status=error\nerror=" + error + "\n", StandardCharsets.UTF_8); }
            catch (Exception ignoredWriteFailure) { error.printStackTrace(); }
        }
    }
}
