"""Port: PolicyEvaluator interface (hexagonal, SOLID).

Defines the interface for policy evaluation, decoupling the core from OPA client implementations.
"""

from abc import ABC, abstractmethod

class PolicyEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, package: str, input_data: dict) -> dict:
        """Evaluate a policy package with input data and return the result."""
        pass
