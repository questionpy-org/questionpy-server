from abc import ABC, abstractmethod
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ByteSize, ConfigDict, StringConstraints


class UserUploadedFile(BaseModel, ABC):
    """Metadata about a file uploaded by a user to the LMS."""

    path: Annotated[str, StringConstraints(pattern=r"^/(.+/)?$")]
    """The folder path of this file. Must begin and end in `/`. Top-level files have a path of `/`."""

    filename: str

    file_ref: str
    """An opaque reference that can be used to retrieve the file content from the LMS."""

    uploaded_at: datetime

    mime_type: str

    size: ByteSize

    @property
    @abstractmethod
    def uri(self) -> str:
        """Builds a URI that can be used to embed the file in a question."""


class ResponseFile(UserUploadedFile):
    @property
    def uri(self) -> str:
        return f"qpy://response/{self.file_ref}"


class OptionsFile(UserUploadedFile):
    @property
    def uri(self) -> str:
        return f"qpy://options/{self.file_ref}"


class EditorData[FileT: UserUploadedFile](BaseModel):
    """Data submitted by rich text editors."""

    # The LMS may send and expect to receive back again additional properties. They must begin with _, though we don't
    # check that restriction yet.
    model_config = ConfigDict(extra="allow")

    text: str
    """The text content of the editor, in whichever markup format the LMS uses."""

    files: list[FileT] = []
    """Files referenced by the markup."""
