"""
API v2 Bulk Host Create — Shape 5 (bulk) module.

This module does NOT use the standard CRUD transform pipeline. The action
plugin resolves the inventory ID and calls the SDK bulk_host_create()
method directly. No API dataclass or transform mixin is needed.
"""
