        if (req.ioctl_cmd == 0x1D) {
            if (req.arg_cnt_in != 1 || req.arg_cnt_out != 1 || req.ioctlv_vecs.size() != 2
                || req.ioctlv_vecs[0].len != 8 || req.ioctlv_vecs[1].len < 30
                || !openshsm::experiment::nand_span(req.ioctlv_vecs[0].addr, 8)
                || !openshsm::experiment::nand_span(req.ioctlv_vecs[1].addr, 30)) {
                return IPC_EINVAL;
            }
            const auto input = openshsm::experiment::nand_virtual(req.ioctlv_vecs[0].addr);
            const auto output = openshsm::experiment::nand_virtual(req.ioctlv_vecs[1].addr);
            const auto path = openshsm::experiment::title_data_path(ctx.mmu.read32(input), ctx.mmu.read32(input + 4));
            for (unsigned i = 0; i <= path.size(); ++i) {
                ctx.mmu.write8(output + i, i == path.size() ? 0 : path[i]);
            }
            std::cout << "[ES directory] " << path << '\n';
            return IPC_OK;
        }
