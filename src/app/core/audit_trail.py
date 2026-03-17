"""Port: AuditTrail interface (hexagonal, SOLID).

Defines the interface for audit trail recording and querying.
"""

from abc import ABC, abstractmethod

class AuditTrail(ABC):
    @abstractmethod
    def record(self, policy: str, result: dict, input_data: dict, meta: dict) -> str:
        """Record an audit event and return its ID."""
        pass

    @abstractmethod
    def query(self, **filters) -> list:
        """Query audit events with filters."""
        pass
