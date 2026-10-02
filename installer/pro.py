"""Commercial boundary: the public Community distribution cannot activate KOS Pro."""
from typing import Protocol

from contracts import canonical_edition
from engine import state_read


class EntitlementProvider(Protocol):
    def permits_acquisition(self, package_id: str, version: str, receipt: dict) -> bool:
        """Verify acquisition rights externally; never revoke installed versions."""
        ...


def pro_plan(root, package=None, receipt=None):
    state = state_read(root)
    reason = "PRO_PACKAGE_UNAVAILABLE" if package is None else "PRO_TRUST_AND_ENTITLEMENT_PROVIDER_UNAVAILABLE"
    if receipt is not None:
        from contracts import check
        check("entitlement", receipt)
    return {
        "schemaVersion": "1.0.0",
        "operation": "pro",
        "targetType": "managed-kos" if state else "legacy-kos",
        "previousVersion": state.get("starterKitVersion") if state else None,
        "resultingVersion": state.get("starterKitVersion") if state else None,
        "edition": canonical_edition(state.get("edition", "community")) if state else "community",
        "blocked": True,
        "items": [{"path": "KOS Pro", "classification": "BLOCKED", "action": "BLOCK", "rule": reason}],
        "requiredAction": "KOS Pro is a separately licensed commercial edition and is not included in the KOS Starter Kit; no files changed.",
    }
