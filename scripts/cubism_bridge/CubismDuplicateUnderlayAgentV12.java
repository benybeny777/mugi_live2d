package mugi.bridge;

import java.lang.instrument.Instrumentation;

/** Parent-registered reserved-atlas underlay entrypoint. */
public final class CubismDuplicateUnderlayAgentV12 {
    public static void agentmain(String argument, Instrumentation instrumentation) {
        CubismDuplicateUnderlayAgentImplV12.agentmain(argument, instrumentation);
    }
}
