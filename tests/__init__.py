"""VERA test suite.

Tests follow a sample-level split convention — never split a single
sample's measurements across train / val / test, since that leaks
composition information through repeated measurements. The
``test_datasets.py`` suite asserts on that invariant.
"""
