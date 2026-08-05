package mugi.bridge;

import java.lang.instrument.Instrumentation;

/** Versioned MOC and texture exporter entrypoint that writes a completion marker. */
public final class CubismMocExportAgentV4 {
    public static void agentmain(String argument, Instrumentation instrumentation) {
        CubismMocExportAgentImplV4.agentmain(argument, instrumentation);
    }
}
