import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportFormatSpan extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        var functions = currentProgram.getFunctionManager().getFunctions(true);
        ghidra.program.model.listing.Function selected = null;
        while (functions.hasNext()) {
            var function = functions.next();
            if (function.getName().equals(args[1])) {
                selected = function;
                break;
            }
        }
        if (selected == null) {
            throw new IllegalStateException("Parser symbol missing");
        }
        int count = Integer.parseInt(args[2]);
        int size = Integer.parseInt(args[3]);
        if (count * 4 != size) {
            throw new IllegalArgumentException("PPC span size mismatch");
        }
        StringBuilder assembly = new StringBuilder();
        for (int index = 0; index < count; ++index) {
            var address = selected.getEntryPoint().add(index * 4);
            var instruction = getInstructionAt(address);
            if (instruction == null) {
                disassemble(address);
                instruction = getInstructionAt(address);
            }
            if (instruction == null || instruction.getLength() != 4) {
                throw new IllegalStateException("Span instruction missing: " + address);
            }
            assembly.append(address).append('\t').append(instruction).append('\n');
        }
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException("Decompiler unavailable");
        }
        var result = decompiler.decompileFunction(selected, 60, monitor);
        if (!result.decompileCompleted()) {
            throw new IllegalStateException(result.getErrorMessage());
        }
        Path output = Path.of(args[0]);
        Files.createDirectories(output);
        Files.writeString(output.resolve(args[1] + ".asm"), assembly.toString());
        Files.writeString(output.resolve(args[1] + ".c"), result.getDecompiledFunction().getC());
        Files.writeString(output.resolve("function-body-bytes.txt"), Long.toString(selected.getBody().getNumAddresses()));
        decompiler.dispose();
        println("SHSM_ROOT_GHIDRA_PASS:" + args[1] + ":" + count + ":" + size);
    }
}
