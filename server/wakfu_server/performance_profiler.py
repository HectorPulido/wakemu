"""Shared server performance diagnostics facade."""
from .storage.performance_profiler import PROFILER, PerformanceProfiler

__all__ = ["PROFILER", "PerformanceProfiler"]
