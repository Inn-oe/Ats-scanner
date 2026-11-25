"""ATS scanner: score a CV against a job advert and suggest improvements."""

from .analyzer import AnalysisResult, analyze
from .parser import extract_text, extract_text_from_path

__all__ = ["analyze", "AnalysisResult", "extract_text", "extract_text_from_path"]
