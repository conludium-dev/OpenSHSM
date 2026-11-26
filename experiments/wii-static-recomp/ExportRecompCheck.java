import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.InstructionIterator;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportRecompCheck extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException("Private output directory required");
        }
        Path output = Path.of(arguments[0]);
        if (!currentProgram.getLanguageID().toString().equals("PowerPC:BE:32:default")) {
            throw new IllegalStateException("Incorrect PPC language variant");
        }
        Files.createDirectories(output);
        Function selected = null;
        FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
        while (functions.hasNext()) {
            Function function = functions.next();
            if (function.getName().equals("fn_800F3E60")) {
                selected = function;
                break;
            }
        }
        if (selected == null) {
            throw new IllegalStateException("Selected SHSM function not found in PPC object");
        }
        StringBuilder text = new StringBuilder();
        int count = 0;
        InstructionIterator instructions = currentProgram.getListing().getInstructions(selected.getBody(), true);
        while (instructions.hasNext()) {
            var instruction = instructions.next();
            text.append(instruction.getAddress()).append('\t').append(instruction).append('\n');
            ++count;
        }
        if (count != 24 || selected.getBody().getNumAddresses() != 96) {
            throw new IllegalStateException("Function boundary/instruction-count mismatch: " + count);
        }
        Files.writeString(output.resolve("ghidra-selected.asm"), text.toString());
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException("Decompiler failed to open program");
        }
        var result = decompiler.decompileFunction(selected, 60, monitor);
        if (!result.decompileCompleted()) {
            throw new IllegalStateException(result.getErrorMessage());
        }
        Files.writeString(output.resolve("ghidra-selected.c"), result.getDecompiledFunction().getC());
        Files.writeString(output.resolve("ghidra-result.txt"), "PASS\nfunction=fn_800F3E60\ninstructions=24\nbytes=96\nlanguage=" +
            currentProgram.getLanguageID() + "\nentry=" + selected.getEntryPoint() + "\n");
        decompiler.dispose();
        println("SHSM_RECOMP_GHIDRA_PASS:24instructions/96bytes/decompiler");
    }
}
