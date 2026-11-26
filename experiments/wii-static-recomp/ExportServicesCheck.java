import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportServicesCheck extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1 || !currentProgram.getLanguageID().toString().equals("PowerPC:BE:32:default")) {
            throw new IllegalStateException("Private output path and PPC32 default language required");
        }
        Path output = Path.of(arguments[0]);
        String[] names = {"fn_800ED314", "fn_800ED3C8"};
        int[] counts = {45, 320};
        StringBuilder report = new StringBuilder("PASS\nlanguage=" + currentProgram.getLanguageID() + "\n");
        for (int index = 0; index < names.length; ++index) {
            Function selected = null;
            var functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                Function candidate = functions.next();
                if (candidate.getName().equals(names[index])) {
                    selected = candidate;
                    break;
                }
            }
            if (selected == null) {
                throw new IllegalStateException("Original PPC object symbol missing: " + names[index]);
            }
            StringBuilder assembly = new StringBuilder();
            for (int word = 0; word < counts[index]; ++word) {
                var address = selected.getEntryPoint().add(word * 4);
                if (currentProgram.getListing().getInstructionAt(address) == null) {
                    disassemble(address);
                }
                var instruction = currentProgram.getListing().getInstructionAt(address);
                if (instruction == null || instruction.getLength() != 4) {
                    throw new IllegalStateException("Original PPC instruction not decoded: " + address);
                }
                assembly.append(address).append('\t').append(instruction).append('\n');
            }
            Files.writeString(output.resolve(names[index] + "-ghidra.asm"), assembly.toString());
            DecompInterface decompiler = new DecompInterface();
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException("Decompiler open failed");
            }
            var result = decompiler.decompileFunction(selected, 60, monitor);
            if (!result.decompileCompleted()) {
                throw new IllegalStateException(result.getErrorMessage());
            }
            Files.writeString(output.resolve(names[index] + "-ghidra.c"), result.getDecompiledFunction().getC());
            report.append(names[index]).append(" instructions=").append(counts[index]).append(" suppliedBytes=")
                  .append(counts[index] * 4).append(" inferredBodyBytes=").append(selected.getBody().getNumAddresses()).append('\n');
            decompiler.dispose();
        }
        Files.writeString(output.resolve("ghidra-services.txt"), report.toString());
        println("SHSM_SERVICES_GHIDRA_PASS:45+320instructions;static_disassembly_not_behavioral_acceptance");
    }
}
