"""Thread-safe dictionary for ResponseFrame objects."""

from threading import Lock
from typing import Any

from freewili.framing import ResponseFrame


class SafeDict:  # noqa: D101
    """A thread-safe dictionary implementation.

    This class provides a dictionary-like interface with thread safety
    using a lock to protect all dictionary operations.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._dict: dict[Any, Any] = {}

    def __len__(self) -> int:
        with self._lock:
            return len(self._dict)

    def __iter__(self) -> Any:
        with self._lock:
            return iter(dict(self._dict))

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._dict

    def get(self, key: Any, default: Any = None) -> Any:  # noqa: D102
        with self._lock:
            return self._dict.get(key, default)

    def items(self) -> list[tuple[Any, Any]]:  # noqa: D102
        with self._lock:
            return list(self._dict.items())

    def values(self) -> list[Any]:  # noqa: D102
        with self._lock:
            return list(self._dict.values())

    def keys(self) -> list[Any]:  # noqa: D102
        with self._lock:
            return list(self._dict.keys())

    def clear(self) -> None:  # noqa: D102
        with self._lock:
            self._dict.clear()

    def update(self, *args: Any, **kwargs: Any) -> None:  # noqa: D102
        with self._lock:
            self._dict.update(*args, **kwargs)

    def setdefault(self, key: Any, default: Any = None) -> Any:  # noqa: D102
        with self._lock:
            return self._dict.setdefault(key, default)

    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            return self._dict[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        with self._lock:
            self._dict[key] = value

    def __delitem__(self, key: Any) -> None:
        with self._lock:
            del self._dict[key]

    def pop(self, key: Any) -> Any:  # noqa: D102
        """Remove and return the value for the given key if it exists."""
        with self._lock:
            return self._dict.pop(key, None)


class SafeResponseFrameDict(SafeDict):
    """A thread-safe dictionary for response frames."""

    def __init__(self) -> None:
        super().__init__()

    def add(self, rf: ResponseFrame) -> None:
        """Add a ResponseFrame to the container."""
        assert isinstance(rf, ResponseFrame), "Expected a ResponseFrame instance"
        self.setdefault(rf.rf_type_data, []).append(rf)
