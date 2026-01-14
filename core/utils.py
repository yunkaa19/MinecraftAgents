import importlib
import pkgutil
import inspect
import os
import time
import functools
import logging
from typing import List, Type, Any

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
                    if inspect.isclass(obj) and issubclass(obj, base_class) and obj is not base_class:
                        classes.append(obj)
            except Exception as e:
                print(f"Error loading module {name}: {e}")
    
    return classes
