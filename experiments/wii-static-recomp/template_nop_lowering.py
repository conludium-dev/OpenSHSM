"""Replace only the independently observed NOP store; retain template entry guards."""
from nop_observer_lowering import lower as observe

def lower(text, dol):
    observed, changes = observe(text, dol)
    for change in changes:
        after = change['after'].replace('experiment_observed_write32', 'experiment_template_nop')
        observed = observed.replace(change['after'], after)
        change['after'] = after
    return observed, changes
