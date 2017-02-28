"""Custom tools for managing JSON serialization / deserialization of xonsh
objects.
"""
import functools

from xonsh.tools import EnvPath


@functools.singledispatch
def serialize_xonsh_json(val):
    """JSON serializer for xonsh custom data structures. This is only
    called when another normal JSON types are not found.
    """
    return str(val)


@serialize_xonsh_json.register(EnvPath)
def _serialize_xonsh_json_env_path(val):
    return val.paths
