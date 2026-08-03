// Force Photoshop to rewrite each raster layer from its transparency channel.
// Applying an equivalent layer mask preserves the visible pixels and layer ID,
// while allowing Photoshop to discard transparent full-canvas storage.
app.displayDialogs = DialogModes.NO;

var source = new File("C:/00_PG/40_mugi_live2d/work/psd/hiyori/mugi-hiyori-compatible-final.psd");
var output = new File("C:/00_PG/40_mugi_live2d/work/psd/hiyori/mugi-hiyori-compatible-photoshop-tight-test.psd");
var logFile = new File("C:/00_PG/40_mugi_live2d/logs/photoshop-tighten-layers.log");

function selectActiveLayerTransparency() {
    var descriptor = new ActionDescriptor();
    var selectionReference = new ActionReference();
    selectionReference.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
    descriptor.putReference(charIDToTypeID("null"), selectionReference);
    var transparencyReference = new ActionReference();
    transparencyReference.putEnumerated(
        charIDToTypeID("Chnl"),
        charIDToTypeID("Chnl"),
        charIDToTypeID("Trsp")
    );
    descriptor.putReference(charIDToTypeID("T   "), transparencyReference);
    executeAction(charIDToTypeID("setd"), descriptor, DialogModes.NO);
}

function createMaskFromSelection() {
    var descriptor = new ActionDescriptor();
    descriptor.putClass(charIDToTypeID("Nw  "), charIDToTypeID("Chnl"));
    var maskReference = new ActionReference();
    maskReference.putEnumerated(
        charIDToTypeID("Chnl"),
        charIDToTypeID("Chnl"),
        charIDToTypeID("Msk ")
    );
    descriptor.putReference(charIDToTypeID("At  "), maskReference);
    descriptor.putEnumerated(
        charIDToTypeID("Usng"),
        charIDToTypeID("UsrM"),
        charIDToTypeID("RvlS")
    );
    executeAction(charIDToTypeID("Mk  "), descriptor, DialogModes.NO);
}

function applyActiveLayerMask() {
    var descriptor = new ActionDescriptor();
    var maskReference = new ActionReference();
    maskReference.putEnumerated(
        charIDToTypeID("Chnl"),
        charIDToTypeID("Chnl"),
        charIDToTypeID("Msk ")
    );
    descriptor.putReference(charIDToTypeID("null"), maskReference);
    descriptor.putBoolean(charIDToTypeID("Aply"), true);
    executeAction(charIDToTypeID("Dlt "), descriptor, DialogModes.NO);
}

function collectArtLayers(container, result) {
    for (var index = 0; index < container.layers.length; index += 1) {
        var layer = container.layers[index];
        if (layer.typename === "ArtLayer") {
            result.push(layer);
        } else if (layer.typename === "LayerSet") {
            collectArtLayers(layer, result);
        }
    }
}

try {
    var documentRef = app.open(source);
    var artLayers = [];
    collectArtLayers(documentRef, artLayers);
    var processed = 0;
    var skipped = 0;
    var errors = [];

    for (var index = 0; index < artLayers.length; index += 1) {
        var layer = artLayers[index];
        documentRef.activeLayer = layer;
        try {
            // The exporter already stores the See-through result as a layer
            // mask. Applying that existing mask bakes the alpha without
            // changing the layer identity used by Cubism's re-import mapping.
            applyActiveLayerMask();
            processed += 1;
        } catch (layerError) {
            skipped += 1;
            if (errors.length < 10) {
                errors.push(layer.name + ": " + layerError.toString());
            }
            documentRef.selection.deselect();
        }
    }

    var options = new PhotoshopSaveOptions();
    options.layers = true;
    options.embedColorProfile = true;
    options.alphaChannels = true;
    options.annotations = false;
    options.spotColors = true;
    documentRef.saveAs(output, options, true, Extension.LOWERCASE);
    documentRef.close(SaveOptions.DONOTSAVECHANGES);

    logFile.open("w");
    logFile.writeln("status=success");
    logFile.writeln("processed=" + processed);
    logFile.writeln("skipped=" + skipped);
    for (var errorIndex = 0; errorIndex < errors.length; errorIndex += 1) {
        logFile.writeln("layer_error=" + errors[errorIndex]);
    }
    logFile.writeln("output=" + output.fsName);
    logFile.close();
} catch (error) {
    logFile.open("w");
    logFile.writeln("status=failed");
    logFile.writeln("error=" + error.toString());
    logFile.close();
    throw error;
}
