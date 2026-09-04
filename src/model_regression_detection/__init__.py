"""Model Regression Detection System."""

from model_regression_detection.classifier import classify_email, load_prompt
from model_regression_detection.config import Settings, get_settings

__all__ = ["Settings", "classify_email", "get_settings", "load_prompt"]
