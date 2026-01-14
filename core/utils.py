import importlib
import pkgutil
import inspect
import time
import functools
import logging
from typing import List, Type, Any
import mcpi.block as block

# Simple mapping for common blocks
BLOCK_ID_MAP = {
    block.STONE.id: "STONE",
    block.COBBLESTONE.id: "COBBLESTONE",
    block.DIRT.id: "DIRT",
    block.GRASS.id: "GRASS",
    block.WOOD_PLANKS.id: "WOOD_PLANKS",
    block.WOOD.id: "WOOD",
    block.SAND.id: "SAND",
    block.GRAVEL.id: "GRAVEL",
    65: "LADDER",
    67: "COBBLESTONE_STAIRS",
    block.GOLD_ORE.id: "GOLD_ORE",
    block.IRON_ORE.id: "IRON_ORE",
    block.COAL_ORE.id: "COAL_ORE",
    block.DIAMOND_ORE.id: "DIAMOND_ORE",
    0: "AIR",
    # Add wood types just in case they are mined directly
    17: "WOOD",
    5: "WOOD_PLANKS",
}

# Materials that can be crafted from other materials
# Target -> {Source Material: Quantity needed}
CRAFTING_RECIPES = {
    "WOOD_PLANKS": {"WOOD": 0.25},  # 1 Wood = 4 Planks
    "TORCH": {
        "COAL_ORE": 0.25,
        "WOOD": 0.1,
    },  # 1 Coal + 1 Stick (from wood) = 4 Torches. Simplified as 0.1 Wood per Torch.
    "COBBLESTONE": {"STONE": 1},
}


def get_block_name(block_id: int) -> str:
    """Returns the name of a block from its ID."""
    return BLOCK_ID_MAP.get(block_id, "UNKNOWN")


def log_execution(func):
    """Decorator to log the execution time of a method."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {duration:.4f}s")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise e

    return wrapper


def load_classes(package_name: str, base_class: Type[Any]) -> List[Type[Any]]:
    """
    Dynamically loads classes from a package that inherit from a base class.

    Args:
        package_name: The name of the package to scan (e.g., 'agents').
        base_class: The class that discovered classes must inherit from.

    Returns:
        A list of discovered classes.
    """
    classes = []
    try:
        package = importlib.import_module(package_name)
    except ImportError as e:
        print(f"Could not import package {package_name}: {e}")
        return []

    # Handle both directory-based packages and simple modules
    if hasattr(package, "__path__"):
        path = package.__path__
        prefix = package.__name__ + "."

        for _, name, _ in pkgutil.iter_modules(path, prefix):
            try:
                module = importlib.import_module(name)
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, base_class)
                        and obj is not base_class
                    ):
                        classes.append(obj)
            except Exception as e:
                print(f"Error loading module {name}: {e}")

    return classes
