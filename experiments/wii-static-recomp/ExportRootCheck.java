import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportRootCheck extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 4) {
            throw new IllegalArgumentException("Output, function name, instruction count and byte size required");
        }
        var iterator = currentProgram.getFunctionManager().getFunctions(true);
        ghidra.program.model.listing.Function selected = null;
        while (iterator.hasNext()) {
            var function = iterator.next();
            if (function.getName().equals(arguments[1])) {
                selected = function;
                break;
            }
        }
        if (selected == null) {
            throw new IllegalStateException("Selected function missing");
        }
        int expectedCount = Integer.parseInt(arguments[2]);
        int expectedBytes = Integer.parseInt(arguments[3]);
        int count = 0;
        StringBuilder assembly = new StringBuilder();
        var instructions = currentProgram.getListing().getInstructions(selected.getBody(), true);
        while (instructions.hasNext()) {
            var instruction = instructions.next();
            assembly.append(instruction.getAddress()).append('\t').append(instruction).append('\n');
            ++count;
        }
        if (count != expectedCount || selected.getBody().getNumAddresses() != expectedBytes) {
            throw new IllegalStateException("Boundary mismatch: " + count + "/" + selected.getBody().getNumAddresses());
        }
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException("Decompiler open failed");
        }
        var result = decompiler.decompileFunction(selected, 60, monitor);
        if (!result.decompileCompleted()) {
            throw new IllegalStateException(result.getErrorMessage());
        }
        Path output = Path.of(arguments[0]);
        Files.createDirectories(output);
        Files.writeString(output.resolve(arguments[1] + ".asm"), assembly.toString());
        Files.writeString(output.resolve(arguments[1] + ".c"), result.getDecompiledFunction().getC());
        decompiler.dispose();
        println("SHSM_ROOT_GHIDRA_PASS:" + arguments[1] + ":" + count + ":" + expectedBytes);
    }
}
