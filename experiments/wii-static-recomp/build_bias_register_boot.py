"""Reuse the existing bulk builder but admit only the newly captured register opcode."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/build_bias_constructors_boot.py')
body = parent.read_text().replace('bias_constructor_lowering','bias_register_variant_lowering').replace(
    'mass-fp-registration-boot','mass-fcmp-finite-boot').replace(
    'mass-bias-constructors-boot','mass-bias-register-boot').replace(
    'audit_fp_registration_boot.py','audit_fcmp_finite_boot.py').replace(
    'SHSM_BIAS_CONSTRUCTORS_DISABLED','SHSM_BIAS_VARIANTS_DISABLED').replace(
    '0x80017480','0x800a8ed8')
marker = "sites = select(dol, 'work/private-game/static-recomp/dtk-output/asm')"
assert body.count(marker) == 1
body = body.replace(marker,marker + "\nsites = [site for site in sites if site['opcode'] == 0xec401828]\nassert len(sites) == 1")
body = body.replace("('audit_fcmp_finite_boot.py',)","('audit_fcmp_finite_boot.py','verify_fsubs_variant.py')")
body = body.replace("'91 static matches do not mean91 whole-function behavioral oracles or completed startup.'",
    "'Only captured EC401828 register variant admitted; other register variants and division/multiplication remain guarded.'")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
