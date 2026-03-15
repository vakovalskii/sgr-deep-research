import logging
from typing import TYPE_CHECKING, Generic, Tuple, TypeVar

if TYPE_CHECKING:
    from sgr_agent_core import (
        BaseAgent,  # noqa: F401
        BaseTool,  # noqa: F401
    )
    from sgr_agent_core.stream import BaseStreamingGenerator  # noqa: F401


logger = logging.getLogger(__name__)

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic registry for managing classes.

    Can be subclassed to create specific registries for different types.
    Each subclass will have its own separate registry storage.
    """

    _items: dict[str, type[T]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._items = {}

    def __init__(self):
        raise TypeError(f"{self.__class__.__name__} is a static class and cannot be instantiated")

    @classmethod
    def register(cls, item_class: type[T] | None = None, name: str | None = None) -> type[T]:
        """Register an item class.

        Can be used as a decorator or called directly:

        As decorator:
            @Registry.register
            class MyClass:
                pass

        As decorator with name:
            @Registry.register(name="custom_name")
            class MyClass:
                pass

        Direct call:
            Registry.register(MyClass)
            Registry.register(MyClass, name="custom_name")

        Args:
            item_class: Class to register (None when used as decorator)
            name: Optional name to register the class under

        Returns:
            The class itself (for decorator usage) or decorator function
        """

        def _register(cls_to_register: type[T]) -> type[T]:
            """Internal registration function."""
            if cls_to_register.__name__ not in cls._items:
                cls._items[cls_to_register.__name__.lower()] = cls_to_register
                if name is not None:
                    cls._items[name.lower()] = cls_to_register
            return cls_to_register

        # Used as decorator without arguments: @Registry.register
        if item_class is not None:
            return _register(item_class)
        return _register

    @classmethod
    def get(cls, name: str) -> type[T] | None:
        """Get a class by name.

        Args:
            name: Name of the class to retrieve

        Returns:
            Class or None if not found
        """
        return cls._items.get(name.lower())

    @classmethod
    def list_items(cls) -> list[type[T]]:
        """Get all registered items.

        Returns:
            List of classes
        """
        return list(set(cls._items.values()))

    @classmethod
    def resolve(cls, names: list[str]) -> Tuple[list[type[T]], list[str]]:
        """Resolve names to classes.

        Args:
            names: List of names to resolve

        Returns:
            List of classes
        """
        items = []
        missing = []
        for name in names:
            if item_class := cls._items.get(name.lower()):
                items.append(item_class)
            else:
                logger.warning(f"Item {name} not found in {cls.__name__}")
                missing.append(name)
                continue
        return items, missing

    @classmethod
    def clear(cls) -> None:
        """Clear all registered items."""
        cls._items.clear()


class AgentRegistry(Registry["BaseAgent"]):
    pass


class ToolRegistry(Registry["BaseTool"]):
    pass


class StreamingGeneratorRegistry(Registry["BaseStreamingGenerator"]):
    """Registry for streaming generator classes (openai, open_webui,
    custom)."""
