"""Core: HandlerRegistry (hexagonal, SOLID).

Explicit registry for event handlers, decoupled from adapters.
"""

class HandlerRegistry:
    def __init__(self):
        self._registry = {}

    def register(self, event_type, handler_func):
        self._registry[event_type] = handler_func

    def get(self, event_type):
        return self._registry.get(event_type)
