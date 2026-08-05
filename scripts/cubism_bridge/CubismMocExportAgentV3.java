package mugi.bridge;

import java.lang.instrument.Instrumentation;

/** Versioned MOC and texture exporter entrypoint. */
public final class CubismMocExportAgentV3 {
    public static void agentmain(String argument, Instrumentation instrumentation) {
        CubismMocExportAgentImplV3.agentmain(argument, instrumentation);
    }
}
