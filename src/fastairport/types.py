"""
Shared Pydantic models, Polars types, and other type aliases for FastAirport.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import polars as pl

# Pydantic re-exports
__all__ = [
    "BaseModel",
    "Field",
    # Python typing re-exports for convenience in user code
    "List",
    "Optional",
    "Dict",
    "Any",
    "Union",
    # Polars re-exports
    "DataFrame",
    "Series",
    "pl",  # Expose the polars module itself as pl
]

# Polars type aliases
DataFrame = pl.DataFrame
Series = pl.Series
