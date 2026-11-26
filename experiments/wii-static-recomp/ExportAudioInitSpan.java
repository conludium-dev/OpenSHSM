import java.nio.file.Files;
import java.nio.file.Path;

public class ExportAudioInitSpan extends ExportFormatSpan {
    @Override
    public void run() throws Exception {
        super.run();
        String[] args = getScriptArgs();
        var functions = currentProgram.getFunctionManager().getFunctions(true);
        while (functions.hasNext()) {
            var function = functions.next();
            if (!function.getName().equals(args[1])) {
                continue;
            }
            StringBuilder membership = new StringBuilder();
            for (int index = 0; index < Integer.parseInt(args[2]); ++index) {
                var address = function.getEntryPoint().add(index * 4);
                membership.append(index * 4).append('\t').append(function.getBody().contains(address)).append('\n');
            }
            Files.writeString(Path.of(args[0]).resolve("body-membership.txt"), membership.toString());
            println("SHSM_AUDIO_MEMBERSHIP_PASS");
            return;
        }
        throw new IllegalStateException("Audio symbol missing after span export");
    }
}
