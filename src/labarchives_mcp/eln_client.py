"""Minimal LabArchives ELN client for PoL purposes."""

from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from datetime import UTC
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from .auth import AuthenticationManager
from .transform import NotebookTransformer

if TYPE_CHECKING:
    from .models.upload import (
        AttachmentUploadRequest,
        AttachmentUploadResult,
        PageCreationRequest,
        PageCreationResult,
        UploadRequest,
        UploadResponse,
    )


class NotebookRecord(BaseModel):
    """Normalized notebook metadata returned to MCP clients.

    This is the source of truth for the notebook resource schema.
    Generate JSON Schema:
        python -c "from labarchives_mcp.eln_client import NotebookRecord;
                   print(NotebookRecord.schema_json(indent=4))"
    """

    nbid: str = Field(
        description="LabArchives notebook ID (base64-encoded)",
        examples=[
            "MTU2MTI4NS43fDEyMDA5ODkvMTIwMDk4OS9Ob3RlYm9vay81MzgyNzU0MDh8Mzk2MzI2My42OTk5OTk5OTk3"
        ],
    )
    name: str = Field(description="Notebook name", examples=["Fly Behavior Study"])
    owner: str = Field(
        description="Owner identifier (typically email)",
        examples=["samuel.brudner@yale.edu"],
    )
    owner_email: str = Field(
        description="Owner email address", examples=["samuel.brudner@yale.edu"]
    )
    owner_name: str = Field(description="Owner full name", examples=["Samuel Brudner"])
    created_at: str = Field(
        alias="created_at",
        description="Notebook creation timestamp (ISO 8601, UTC)",
        examples=["2025-01-01T12:00:00Z"],
    )
    modified_at: str = Field(
        alias="modified_at",
        description="Last modification timestamp (ISO 8601, UTC)",
        examples=["2025-01-02T08:30:00Z"],
    )


class LabArchivesClient:
    """Wrap LabArchives ELN API calls needed for proof-of-life."""

    def __init__(self, client: httpx.AsyncClient, auth_manager: AuthenticationManager) -> None:
        self._client = client
        self._auth_manager = auth_manager

    @staticmethod
    def _markdown_to_html(markdown_text: str, require_lib: bool = False) -> str:
        """Convert Markdown to HTML.

        Tries to use the `markdown` package if available; falls back to a
        lightweight converter handling common constructs (headings, lists,
        bold/italic, code blocks, inline code, paragraphs).
        """
        try:
            import markdown as _md  # type: ignore[import-untyped]

            return str(
                _md.markdown(
                    markdown_text,
                    extensions=[
                        "fenced_code",
                        "tables",
                        "sane_lists",
                        "toc",
                        "attr_list",
                        "codehilite",
                    ],
                    output_format="html5",
                )
            )
        except Exception as e:
            if require_lib:
                raise RuntimeError(
                    "High-fidelity Markdown conversion requires the 'markdown' package. "
                    "Install it (e.g., 'pip install markdown' or add to your environment)"
                ) from e
            # Fall back to a lightweight converter with a warning
            logger.warning(
                f"High-fidelity Markdown conversion not available ({e}); using fallback converter."
            )

        text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")

        # Handle fenced code blocks first to avoid interfering with other rules
        code_blocks: list[str] = []

        def _codeblock_repl(match: re.Match[str]) -> str:
            lang = match.group(1) or ""
            code = match.group(2)
            escaped = _html.escape(code)
            code_blocks.append(f'<pre><code class="language-{lang}">{escaped}</code></pre>')
            return f"[[CODEBLOCK:{len(code_blocks)-1}]]"

        text = re.sub(r"```([\w+-]*)\n([\s\S]*?)\n```", _codeblock_repl, text)

        # Headings
        def _mk_heading_replacer(level: int) -> Callable[[re.Match[str]], str]:
            def _repl(m: re.Match[str]) -> str:
                content = m.group(1).strip()
                return f"<h{level}>{content}</h{level}>"

            return _repl

        for level in range(6, 0, -1):
            pattern = re.compile(rf"^{'#' * level} +(.+)$", re.MULTILINE)
            text = pattern.sub(_mk_heading_replacer(level), text)

        # Unordered lists (simple): group consecutive - or * items
        lines = text.split("\n")
        out_lines: list[str] = []
        in_list = False
        for line in lines:
            m = re.match(r"^[\-*] +(.*)$", line)
            if m:
                if not in_list:
                    out_lines.append("<ul>")
                    in_list = True
                out_lines.append(f"<li>{m.group(1).strip()}</li>")
            else:
                if in_list:
                    out_lines.append("</ul>")
                    in_list = False
                out_lines.append(line)
        if in_list:
            out_lines.append("</ul>")
        text = "\n".join(out_lines)

        # Inline code
        text = re.sub(r"`([^`]+)`", lambda m: f"<code>{_html.escape(m.group(1))}</code>", text)

        # Bold and italic (basic non-greedy)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)

        # Paragraphs: wrap non-HTML lines separated by blank lines
        blocks = [b.strip() for b in text.split("\n\n")]
        wrapped_blocks: list[str] = []
        for b in blocks:
            if not b:
                continue
            if b.startswith("<h") or b.startswith("<ul>") or b.startswith("<pre>"):
                wrapped_blocks.append(b)
            else:
                wrapped_blocks.append(f"<p>{b}</p>")
        html = "\n\n".join(wrapped_blocks)

        # Restore code blocks placeholders
        def _restore_code(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            return code_blocks[idx]

        html = re.sub(r"\[\[CODEBLOCK:(\d+)\]\]", _restore_code, html)
        return html

    async def list_notebooks(self, uid: str) -> list[NotebookRecord]:
        """Return notebooks for a user uid."""
        auth_params = self._auth_manager._build_auth_params("user_info_via_id")
        params = {"uid": uid, **auth_params}

        response = await self._client.get(
            "https://api.labarchives.com/api/users/user_info_via_id",
            params=params,
        )
        response.raise_for_status()

        payload = response.text
        raw_records = self.parse_xml(payload)
        logger.info(f"Retrieved {len(raw_records)} notebooks for user")

        notebooks: list[NotebookRecord] = []
        for raw in raw_records:
            try:
                notebooks.append(NotebookRecord.model_validate(raw))
            except ValidationError as exc:
                logger.error(f"Notebook validation failed: {exc}")
                raise ValueError("Invalid notebook record received from LabArchives") from exc

        return notebooks

    @staticmethod
    def parse_xml(payload: str) -> list[dict[str, Any]]:
        """Parse LabArchives notebook XML into dictionaries."""

        return NotebookTransformer.parse_notebook_list(payload)

    async def get_notebook_tree(
        self, uid: str, nbid: str, parent_tree_id: int | str = 0
    ) -> list[dict[str, Any]]:
        """Get one level of the notebook tree structure.

        Args:
            uid: User ID
            nbid: Notebook ID
            parent_tree_id: Either 0 for root, or a base64-encoded tree_id string
        """
        logger.debug(f"get_notebook_tree: nbid={nbid}, parent_tree_id={parent_tree_id}")

        auth_params = self._auth_manager._build_auth_params("get_tree_level")
        params = {"uid": uid, "nbid": nbid, "parent_tree_id": str(parent_tree_id), **auth_params}

        url = "https://api.labarchives.com/api/tree_tools/get_tree_level"
        logger.debug(f"Making API request to {url}")

        response = await self._client.get(url, params=params)
        logger.debug(f"API response status: {response.status_code}")
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        nodes = root.findall(".//level-node")
        logger.debug(f"Parsed {len(nodes)} nodes from XML response")

        return [
            {
                "tree_id": node.findtext("tree-id"),
                "display_text": node.findtext("display-text"),
                "is_page": node.findtext("is-page") == "true",
                "is_folder": node.findtext("is-page") != "true",
            }
            for node in nodes
        ]

    async def get_page_entries(
        self, uid: str, nbid: str, page_tree_id: int | str, include_data: bool = True
    ) -> list[dict[str, Any]]:
        """Get all entries for a specific page with their content.

        Args:
            uid: User ID
            nbid: Notebook ID
            page_tree_id: Either an integer or base64-encoded tree_id string
            include_data: Whether to include entry content
        """
        logger.debug(
            f"get_page_entries: nbid={nbid}, page_tree_id={page_tree_id}, "
            f"include_data={include_data}"
        )

        auth_params = self._auth_manager._build_auth_params("get_entries_for_page")
        params = {
            "uid": uid,
            "nbid": nbid,
            "page_tree_id": str(page_tree_id),
            "entry_data": "true" if include_data else "false",
            **auth_params,
        }

        url = "https://api.labarchives.com/api/tree_tools/get_entries_for_page"
        logger.debug(f"Making API request to {url}")

        response = await self._client.get(url, params=params)
        logger.debug(f"API response status: {response.status_code}")
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        entry_elements = root.findall(".//entry")
        logger.debug(f"Parsed {len(entry_elements)} entries from XML response")

        entries = []
        for entry in entry_elements:
            entry_dict = {
                "eid": entry.findtext("eid"),
                "part_type": entry.findtext("part-type"),
                "created_at": entry.findtext("created-at"),
                "updated_at": entry.findtext("updated-at"),
            }
            if include_data:
                entry_data = entry.find("entry-data")
                if entry_data is not None and entry_data.text:
                    entry_dict["content"] = entry_data.text
            entries.append(entry_dict)

        return entries

    async def insert_node(self, uid: str, request: PageCreationRequest) -> PageCreationResult:
        """Create a new page or folder in notebook hierarchy.

        Args:
            uid: User ID
            request: Page creation parameters

        Returns:
            PageCreationResult with tree_id and metadata
        """
        from labarchives_mcp.models.upload import PageCreationResult

        logger.debug(
            f"insert_node: nbid={request.notebook_id}, "
            f"parent={request.parent_tree_id}, display_text={request.display_text}"
        )

        auth_params = self._auth_manager._build_auth_params("insert_node")
        params = {
            "uid": uid,
            "nbid": request.notebook_id,
            "parent_tree_id": str(request.parent_tree_id),
            "display_text": request.display_text,
            "is_folder": "true" if request.is_folder else "false",
            **auth_params,
        }

        url = "https://api.labarchives.com/api/tree_tools/insert_node"
        response = await self._client.post(url, params=params)
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        node = root.find(".//node")

        if node is None:
            raise ValueError("No node returned in insert_node response")

        return PageCreationResult(
            tree_id=node.findtext("tree-id") or "",
            display_text=node.findtext("display-text") or "",
            is_page=node.findtext("is-page") == "true",
        )

    async def add_attachment(
        self, uid: str, request: AttachmentUploadRequest
    ) -> AttachmentUploadResult:
        """Upload a file as attachment to a page.

        Args:
            uid: User ID
            request: Attachment upload parameters

        Returns:
            AttachmentUploadResult with entry metadata
        """
        from datetime import datetime

        from labarchives_mcp.models.upload import AttachmentUploadResult

        logger.debug(
            f"add_attachment: nbid={request.notebook_id}, "
            f"pid={request.page_tree_id}, filename={request.filename}"
        )

        # Read file content
        file_content = request.file_path.read_bytes()
        file_size = len(file_content)

        auth_params = self._auth_manager._build_auth_params("add_attachment")
        # Default filename to file_path.name if not provided
        filename = request.filename or request.file_path.name
        params = {
            "uid": uid,
            "nbid": request.notebook_id,
            "pid": request.page_tree_id,
            "filename": filename,
            **auth_params,
        }

        if request.caption:
            params["caption"] = request.caption
        if request.change_description:
            params["change_description"] = request.change_description

        url = "https://api.labarchives.com/api/entries/add_attachment"
        response = await self._client.post(
            url,
            params=params,
            content=file_content,
            headers={"Content-Type": "application/octet-stream"},
        )
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        entry = root.find(".//entry")

        if entry is None:
            raise ValueError("No entry returned in add_attachment response")

        created_at_str = entry.findtext("created-at")
        created_at = (
            datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at_str
            else datetime.now(UTC)
        )

        return AttachmentUploadResult(
            eid=entry.findtext("eid") or "",
            filename=entry.findtext("filename") or filename,
            caption=entry.findtext("caption"),
            created_at=created_at,
            file_size_bytes=file_size,
        )

    async def add_entry(
        self,
        uid: str,
        notebook_id: str,
        page_tree_id: str,
        part_type: str,
        entry_data: str,
        caption: str | None = None,
        change_description: str | None = None,
    ) -> dict[str, str]:
        """Add a text entry to a page.

        Args:
            uid: User ID
            notebook_id: Notebook ID
            page_tree_id: Page tree_id
            part_type: "text entry", "plain text entry", or "heading"
            entry_data: Content (HTML or plain text)
            caption: Optional caption
            change_description: Optional audit message

        Returns:
            Dictionary with entry metadata
        """
        logger.debug(f"add_entry: nbid={notebook_id}, pid={page_tree_id}, type={part_type}")

        auth_params = self._auth_manager._build_auth_params("add_entry")
        params = {
            "uid": uid,
            "nbid": notebook_id,
            "pid": page_tree_id,
            "part_type": part_type,
            "entry_data": entry_data,
            **auth_params,
        }

        if caption:
            params["caption"] = caption
        if change_description:
            params["change_description"] = change_description

        url = "https://api.labarchives.com/api/entries/add_entry"
        response = await self._client.post(url, params=params)
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        entry = root.find(".//entry")

        if entry is None:
            raise ValueError("No entry returned in add_entry response")

        result: dict[str, str] = {
            "eid": entry.findtext("eid") or "",
            "part_type": entry.findtext("part-type") or part_type,
        }
        created_at_val = entry.findtext("created-at")
        if created_at_val:
            result["created_at"] = created_at_val
        return result

    async def upload_to_labarchives(self, uid: str, request: UploadRequest) -> UploadResponse:
        """Orchestrate complete upload workflow.

        Creates a page and either:
        - Adds the file contents as a page text entry (if request.create_as_text is True), or
        - Uploads the file as an attachment (default behavior).

        Always adds a provenance metadata entry when provided.

        Args:
            uid: User ID
            request: Complete upload request

        Returns:
            UploadResponse with page URL and metadata
        """
        from labarchives_mcp.models.upload import (
            AttachmentUploadRequest,
            PageCreationRequest,
            UploadResponse,
        )

        logger.info(f"upload_to_labarchives: {request.file_path.name}")

        # Validate metadata requirements
        file_suffix = request.file_path.suffix.lower()
        requires_metadata = file_suffix in [".ipynb", ".py", ".r", ".jl", ".m"]

        if requires_metadata and request.metadata is None:
            raise ValueError(
                f"Metadata is required for {file_suffix} files. "
                "Provide ProvenanceMetadata with Git commit SHA, branch, and execution context."
            )

        # Validate dirty Git state
        if request.metadata and request.metadata.git_is_dirty and not request.allow_dirty_git:
            raise ValueError(
                "Cannot upload with uncommitted changes. "
                "Either commit your changes or set allow_dirty_git=True."
            )

        # Step 1: Create page
        page_request = PageCreationRequest(
            notebook_id=request.notebook_id,
            parent_tree_id=request.parent_folder_id or 0,
            display_text=request.page_title,
            is_folder=False,
        )
        page_result = await self.insert_node(uid, page_request)
        logger.info(f"Created page: {page_result.tree_id}")

        # Step 2: Either add file as page text or upload as attachment
        main_entry_eid: str
        filename_for_response: str = request.file_path.name
        file_size_bytes_for_response: int
        created_entry_dict: dict[str, str] | None = None
        from datetime import datetime as dt

        attachment_created_at: dt | None = None

        if request.create_as_text:
            # Read file content as text (best-effort decoding)
            raw_bytes = request.file_path.read_bytes()
            try:
                file_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                file_text = raw_bytes.decode("latin-1", errors="replace")

            # Choose entry type based on extension
            suffix = request.file_path.suffix.lower()
            if suffix in {".html", ".htm"}:
                part_type = "text entry"
                entry_body = file_text
            elif suffix in {".md", ".markdown"}:
                part_type = "text entry"
                entry_body = self._markdown_to_html(file_text, require_lib=True)
            else:
                part_type = "plain text entry"
                entry_body = file_text

            created = await self.add_entry(
                uid=uid,
                notebook_id=request.notebook_id,
                page_tree_id=page_result.tree_id,
                part_type=part_type,
                entry_data=entry_body,
                caption=request.caption,
                change_description=request.change_description,
            )
            main_entry_eid = created["eid"]
            created_entry_dict = created
            file_size_bytes_for_response = len(raw_bytes)
            logger.info(f"Added page text entry: {main_entry_eid}")
        else:
            # Upload as attachment (default)
            attachment_request = AttachmentUploadRequest(
                notebook_id=request.notebook_id,
                page_tree_id=page_result.tree_id,
                file_path=request.file_path,
                filename=request.file_path.name,  # Will be defaulted by model
                caption=request.caption,
                change_description=request.change_description,
            )
            attachment_result = await self.add_attachment(uid, attachment_request)
            main_entry_eid = attachment_result.eid
            file_size_bytes_for_response = attachment_result.file_size_bytes
            attachment_created_at = attachment_result.created_at
            logger.info(f"Uploaded attachment: {main_entry_eid}")

        # Step 3: Add metadata entry if provided
        if request.metadata:
            metadata_markdown = request.metadata.to_markdown()
            await self.add_entry(
                uid=uid,
                notebook_id=request.notebook_id,
                page_tree_id=page_result.tree_id,
                part_type="plain text entry",
                entry_data=metadata_markdown,
                caption="Code Provenance Metadata",
            )
            logger.info("Added metadata entry")

        # Construct canonical page URL (not attachment URL)
        page_url = (
            f"https://mynotebook.labarchives.com/share/{request.notebook_id}/{page_result.tree_id}"
        )

        from datetime import UTC

        if request.create_as_text:
            if created_entry_dict and isinstance(created_entry_dict.get("created_at"), str):
                created_at_dt = dt.fromisoformat(
                    created_entry_dict["created_at"].replace("Z", "+00:00")
                )
            else:
                created_at_dt = dt.now(UTC)
        else:
            # mypy: attachment_created_at is set in the attachment branch
            assert attachment_created_at is not None
            created_at_dt = attachment_created_at

        return UploadResponse(
            page_tree_id=page_result.tree_id,
            entry_id=main_entry_eid,
            page_url=page_url,
            created_at=created_at_dt,
            file_size_bytes=file_size_bytes_for_response,
            filename=filename_for_response,
        )
