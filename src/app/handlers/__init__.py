from ..core.handler_registry import HandlerRegistry

# Global registry instance
handler_registry = HandlerRegistry()

def register_handler(event_type, handler_func):
    handler_registry.register(event_type, handler_func)

def get_handler(event_type):
    return handler_registry.get(event_type)
