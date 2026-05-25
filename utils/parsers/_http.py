# -*- coding: utf-8 -*-
import asyncio
import threading
from typing import Any, Dict, Optional

import requests

_shared_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def get_shared_session() -> requests.Session:
    global _shared_session
    if _shared_session is None:
        with _session_lock:
            if _shared_session is None:
                _shared_session = requests.Session()
    return _shared_session


def close_shared_session() -> None:
    global _shared_session
    with _session_lock:
        if _shared_session is not None:
            _shared_session.close()
            _shared_session = None


async def async_get(url: str, **kwargs: Any) -> requests.Response:
    session = get_shared_session()

    def _sync_get() -> requests.Response:
        return session.get(url, **kwargs)

    return await asyncio.to_thread(_sync_get)


async def async_post(url: str, **kwargs: Any) -> requests.Response:
    session = get_shared_session()

    def _sync_post() -> requests.Response:
        return session.post(url, **kwargs)

    return await asyncio.to_thread(_sync_post)
