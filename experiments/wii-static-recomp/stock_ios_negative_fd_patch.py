"""Avoid materializing IOS vectors when the existing kernel rejects a negative fd."""


def adapt(source):
    marker = '''  uint32_t arg_array = ctx.gpr[7];

  req.arg_cnt_in = arg_in;
'''
    if source.count(marker) != 1:
        raise ValueError('IOS async vector patch site differs')
    replacement = '''  uint32_t arg_array = ctx.gpr[7];

  if (fd < 0) {
    req.arg_cnt_in = arg_in;
    req.arg_cnt_out = arg_out;
    result = IOSKernel::get().ioctlv(ctx, req);
    if (result != IPC_NO_REPLY && nwii::runtime::valid_callback(callback)) {
        ctx.queue_callback(callback, result, userdata);
    }
    ctx.gpr[3] = IPC_OK;
    ctx.pc = ctx.lr;
    return;
  }

  req.arg_cnt_in = arg_in;
'''
    return source.replace(marker, replacement, 1)
