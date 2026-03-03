"""Performance timing utilities for measuring execution time.

This module provides utilities for measuring and logging execution time
at different stages of the operation pipeline.
"""

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TimingMetrics:
    """Container for timing metrics."""
    action_plugin_start: float = 0.0
    action_plugin_end: float = 0.0
    rpc_call_start: float = 0.0
    rpc_call_end: float = 0.0
    manager_processing_start: float = 0.0
    manager_processing_end: float = 0.0
    api_call_start: float = 0.0
    api_call_end: float = 0.0
    total_time: float = 0.0
    action_plugin_time: float = 0.0
    rpc_time: float = 0.0
    manager_processing_time: float = 0.0
    api_call_time: float = 0.0
    other_time: float = 0.0

    def calculate(self):
        """Calculate derived metrics."""
        self.total_time = self.action_plugin_end - self.action_plugin_start
        self.action_plugin_time = self.rpc_call_start - self.action_plugin_start
        self.rpc_time = self.rpc_call_end - self.rpc_call_start
        self.manager_processing_time = self.manager_processing_end - self.manager_processing_start
        self.api_call_time = self.api_call_end - self.api_call_start
        self.other_time = self.total_time - (
            self.action_plugin_time +
            self.rpc_time +
            self.manager_processing_time +
            self.api_call_time
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            'total_time': self.total_time,
            'action_plugin_time': self.action_plugin_time,
            'rpc_time': self.rpc_time,
            'manager_processing_time': self.manager_processing_time,
            'api_call_time': self.api_call_time,
            'other_time': self.other_time,
            'action_plugin_percent': (self.action_plugin_time / self.total_time * 100) if self.total_time > 0 else 0,
            'rpc_percent': (self.rpc_time / self.total_time * 100) if self.total_time > 0 else 0,
            'manager_percent': (self.manager_processing_time / self.total_time * 100) if self.total_time > 0 else 0,
            'api_call_percent': (self.api_call_time / self.total_time * 100) if self.total_time > 0 else 0,
        }


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, operation_name: str, log_level: int = logging.DEBUG):
        self.operation_name = operation_name
        self.log_level = log_level
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.log(
            self.log_level,
            "⏱️  TIMING START: %s (timestamp: %s)",
            self.operation_name, self.start_time
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        elapsed = self.end_time - self.start_time
        logger.log(
            self.log_level,
            "⏱️  TIMING END: %s (elapsed: %ss, timestamp: %s)",
            self.operation_name, elapsed, self.end_time
        )
        return False

    @property
    def elapsed(self) -> float:
        """Get elapsed time."""
        if self.start_time is None:
            return 0.0
        if self.end_time is None:
            return time.perf_counter() - self.start_time
        return self.end_time - self.start_time


def get_timestamp() -> float:
    """Get current high-resolution timestamp."""
    return time.perf_counter()


def log_timing(operation: str, start_time: float, end_time: Optional[float] = None):
    """Log timing information."""
    if end_time is None:
        end_time = time.perf_counter()

    elapsed = end_time - start_time
    logger.debug(
        "⏱️  TIMING: %s | Start: %s | End: %s | Elapsed: %ss",
        operation, start_time, end_time, elapsed
    )
    return elapsed
