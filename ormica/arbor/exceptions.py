"""Exceptions raised by arbor operations."""


class ArborError(Exception):
    """Base class for all arbor errors."""


class MaxDepthExceeded(ArborError):
    """Spawning would push the tree past its configured maximum depth."""


class SpawnDenied(ArborError):
    """The active SpawnPolicy rejected a spawn request."""


class NodeNotFound(ArborError):
    """A node id or reference is not part of the tree."""
