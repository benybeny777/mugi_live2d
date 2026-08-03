// Re-save the original Cubism PSD through Photoshop so layer identities are
// retained while Photoshop rewrites transparent layer storage efficiently.
app.displayDialogs = DialogModes.NO;

var source = new File("C:/00_PG/40_mugi_live2d/work/psd/hiyori/mugi-hiyori-compatible-fullcanvas-backup.psd");
var output = new File("C:/00_PG/40_mugi_live2d/work/psd/hiyori/mugi-hiyori-compatible-final.psd");
var logFile = new File("C:/00_PG/40_mugi_live2d/logs/photoshop-resave-psd.log");

try {
    var documentRef = app.open(source);
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
    logFile.writeln("source=" + source.fsName);
    logFile.writeln("output=" + output.fsName);
    logFile.close();
} catch (error) {
    logFile.open("w");
    logFile.writeln("status=failed");
    logFile.writeln("error=" + error.toString());
    logFile.close();
    throw error;
}
