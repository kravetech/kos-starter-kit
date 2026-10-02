"""Compatibility module for the pre-hierarchy commercial operation name."""
from pro import EntitlementProvider, pro_plan


def core_plan(root, package=None, receipt=None):
    """Map the legacy operation to KOS Pro; KOS Core is architecture, not an edition."""
    return pro_plan(root, package, receipt)
