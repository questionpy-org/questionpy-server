#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import ClientError, ClientResponse, ClientSession

from questionpy_server.repository.helper import DownloadError, download


async def test_raises_download_error_on_client_error() -> None:
    with patch.object(ClientSession, "get", side_effect=ClientError), pytest.raises(DownloadError):
        await download("https://example.com")


async def test_raises_download_error_on_hash_missmatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aiohttp, "ClientSession", AsyncMock(spec=ClientSession))
    with patch.object(ClientResponse, "content") as mock:
        mock.return_value = AsyncMock(return_value=b"data")
        with pytest.raises(DownloadError, match="hash does not match expected hash"):
            await download("https://example.com", expected_hash="expected hash")
