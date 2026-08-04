import com.sun.tools.attach.VirtualMachine;

public final class AttachAgent {
    public static void main(String[] args) throws Exception {
        VirtualMachine machine = VirtualMachine.attach(args[0]);
        try {
            machine.loadAgent(args[1], args[2]);
        } finally {
            machine.detach();
        }
    }
}
