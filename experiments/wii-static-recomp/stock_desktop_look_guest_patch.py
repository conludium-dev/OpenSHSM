"""Add PC direct-look hooks at verified Wii player/camera instruction boundaries."""
import re
import struct


SITES = {
    7: {
        0x8005C85C: (0x39610030, 'flashlight_arm_target'),
        0x8005D31C: (0x9421FEC0, 'begin'),
        0x8005DAFC: (0xD07111B4, 'player_axis'),
        0x8005DB4C: (0xC09111B4, 'restore_axis'),
        0x8005E40C: (0x880F1360, 'qte_apply'),
        0x8005E514: (0x88111571, 'qte_finish'),
        0x8005F4D8: (0x880E0075, 'qte_ttgrab'),
        0x8006166C: (0x482414F9, 'yaw_angle'),
        0x80061714: (0x4182019C, 'yaw_follow'),
    },
    8: {
        0x80071588: (0xD3FD1540, 'flashlight_ray'),
    },
    15: {
        0x800D2908: (0x801C0098, 'hide_look_cursor'),
    },
    16: {
        0x800D48C8: (0x9421FFE0, 'inspection_end'),
        0x800D558C: (0x9421FF10, 'inspection_begin'),
        0x800D5910: (0xC0E293A8, 'inspection_apply'),
    },
    17: {
        0x800EC7E4: (0x2C030000, 'menu_focus'),
        0x800EB5EC: (0x9421FED0, 'qte_gui_reset'),
        0x800EBA8C: (0x48020441, 'qte_gui_enter_primary'),
        0x800EBA90: (0x3BBDFFDC, 'qte_gui_leave_primary'),
        0x800EBB10: (0x9421FC40, 'qte_gui_reset'),
        0x800EC6EC: (0x4801F7E1, 'qte_gui_enter_secondary'),
        0x800EC6F0: (0x3BFFFFDC, 'qte_gui_leave_secondary'),
    },
    19: {
        0x8010C480: (0x39610060, 'qte_gui_draw'),
        0x801161A0: (0x48000498, 'camera_snapshot'),
        0x801192B4: (0xC0E29A24, 'camera_pitch'),
        0x80119E34: (0x396102C0, 'camera_inactive'),
    },
    20: {
        0x8011BCE8: (0x88030150, 'pov_begin'),
        0x8011BD5C: (0xC01F019C, 'pov_apply'),
        0x8011C184: (0x481869E1, 'pov_yaw'),
    },
    24: {
        0x80155FE8: (0x2C030000, 'flashlight_gate'),
        0x8015674C: (0xC03D014C, 'flashlight_direction'),
    },
    26: {
        0x80160E10: (0x88E40058, 'interaction_grab'),
        0x80160E6C: (0x88040058, 'interaction_release'),
    },
    27: {
        0x801725E8: (0x808DA9F8, 'spline_capture'),
        0x80172764: (0x80010034, 'spline_complete'),
    },
    28: {
        0x80176B20: (0x4812FBD9, 'twist_current_sample'),
    },
}


def adapt(text, dol, index):
    header = struct.unpack('>64I', dol[:256])
    for address, (expected, method) in SITES[index].items():
        section = next(i for i in range(18) if header[18 + i] <= address
            and address + 4 <= header[18 + i] + header[36 + i])
        word = struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]
        marker = f'loc_{address:08X}: ;\n'
        copies = 1
        if method == 'twist_current_sample':
            owners = [name for name, body in re.findall(
                r'void func_([0-9A-F]{8})\(CPUContext& ctx\) \{(.*?)(?=\nvoid func_|\Z)', text, re.S)
                if marker in body]
            if owners != ['8017655C', '80177834', '8017785C']:
                raise ValueError('Original Wii twist function aliases differ')
            copies = 3
        if word != expected or text.count(marker) != copies or f'// 0x{address:08X}: {word:08X}' not in text:
            raise ValueError(f'PC look original Wii hook changed: {address:08X}')
        call = (f'openshsm::experiment::primary_desktop_qte_runtime().{method[4:]}(ctx)'
            if method.startswith('qte_') else f'openshsm::experiment::primary_desktop_look_runtime().{method}(ctx)')
        if method == 'twist_current_sample':
            call = 'openshsm::experiment::desktop_twist_current_sample(ctx)'
        if method == 'pov_apply':
            if text.count('loc_8011BFE8: ;\n') != 1:
                raise ValueError('Original Wii POV matrix boundary differs')
            insertion = f'    if ({call}) {{ goto loc_8011BFE8; }}\n'
        elif method == 'qte_ttgrab':
            if text.count('loc_8005F508: ;\n') != 1 or text.count('loc_8005F5A8: ;\n') != 1:
                raise ValueError('Original Wii special-grab branches differ')
            insertion = ('    {\n'
                f'        const int choice = {call};\n'
                '        if (choice > 0) { goto loc_8005F508; }\n'
                '        if (choice == 0) { goto loc_8005F5A8; }\n'
                '    }\n')
        elif method == 'hide_look_cursor':
            if text.count('loc_800D2D84: ;\n') != 1:
                raise ValueError('Original Wii cursor epilogue differs')
            insertion = f'    if ({call}) {{ goto loc_800D2D84; }}\n'
        elif method == 'menu_focus':
            if text.count('loc_800EC8E4: ;\n') != 1:
                raise ValueError('Original Wii menu focus continuation differs')
            insertion = f'    if ({call}) {{ goto loc_800EC8E4; }}\n'
        elif method in ('qte_gui_reset', 'qte_gui_draw'):
            insertion = f'    if ({call}) {{ return; }}\n'
        else:
            insertion = f'    if ({call}) {{ return; }}\n' if method.startswith('interaction_') else f'    {call};\n'
        text = text.replace(marker, marker + insertion, copies)
    includes = '#include "stock_desktop_look_bridge.h"\n'
    if index in (7, 17, 19):
        includes += '#include "stock_desktop_qte_bridge.h"\n'
    return includes + text


def adapt_qte_dispatch(text, dol):
    address = 0x8010C480
    header = struct.unpack('>64I', dol[:256])
    section = next(i for i in range(18) if header[18 + i] <= address
        and address + 4 <= header[18 + i] + header[36 + i])
    word = struct.unpack_from('>I', dol, header[section] + address - header[18 + section])[0]
    before = '    {0x8010C47C, func_8010C30C},\n    {0x8010C4A0, func_8010C30C},'
    if word != SITES[19][address][0] or text.count(before) != 1 or '{0x8010C480,' in text:
        raise ValueError('Original QTE Grid dispatch boundary differs')
    return text.replace(before, '    {0x8010C47C, func_8010C30C},\n'
        '    {0x8010C480, func_8010C30C},\n    {0x8010C4A0, func_8010C30C},')
