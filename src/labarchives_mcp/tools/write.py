"""LabArchives write and upload tools."""

from __future__ import annotations

import asyncio
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..models.upload import PageCreationRequest, ProvenanceMetadata, UploadRequest
from .context import ToolContext
from .decorators import tool


async def upload_to_labarchives(
    context: ToolContext,
    notebook_id: str,
    page_title: str,
    file_path: str,
    git_commit_sha: str,
    git_branch: str,
    git_repo_url: str,
    python_version: str,
    executed_at: str,
    parent_folder_id: str | None = None,
    caption: str | None = None,
    git_is_dirty: bool = False,
    allow_dirty_git: bool = False,
    dependencies: dict[str, str] | None = None,
    as_page_text: bool = True,
) -> dict[str, Any]:
    """Upload a file to LabArchives with code provenance metadata."""
    logger.info(
        f"upload_to_labarchives called: file={file_path}, notebook={notebook_id}, "
        f"title={page_title}"
    )

    try:
        uid = await context.auth_manager.ensure_uid()
        logger.debug(f"Obtained UID: {uid[:20]}...")

        file_path_obj = Path(file_path)
        if not await asyncio.to_thread(file_path_obj.exists):
            raise FileNotFoundError(f"File not found: {file_path}")

        executed_at_dt = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))

        metadata = ProvenanceMetadata(
            git_commit_sha=git_commit_sha,
            git_branch=git_branch,
            git_repo_url=git_repo_url,
            git_is_dirty=git_is_dirty,
            code_version=context.server_version,
            executed_at=executed_at_dt,
            python_version=python_version,
            dependencies=dependencies or {},
            os_name=platform.system(),
            hostname=platform.node(),
        )

        upload_request = UploadRequest(
            notebook_id=notebook_id,
            parent_folder_id=parent_folder_id,
            page_title=page_title,
            file_path=file_path_obj,
            caption=caption,
            change_description=None,
            metadata=metadata,
            allow_dirty_git=allow_dirty_git,
            create_as_text=as_page_text,
        )

        result = await context.notebook_client.upload_to_labarchives(uid, upload_request)
        context.state_manager.record_upload_provenance(
            uid=uid,
            notebook_id=notebook_id,
            page_title=page_title,
            file_path=file_path_obj,
            page_tree_id=result.page_tree_id,
            entry_id=result.entry_id,
            page_url=result.page_url,
            created_at=result.created_at,
            file_size_bytes=result.file_size_bytes,
            filename=result.filename,
            metadata=metadata,
            server_version=context.server_version,
            as_page_text=as_page_text,
        )
        logger.success(f"Successfully uploaded {result.filename} to page {result.page_tree_id}")

        return {
            "page_tree_id": result.page_tree_id,
            "entry_id": result.entry_id,
            "page_url": result.page_url,
            "created_at": result.created_at.isoformat(),
            "file_size_bytes": result.file_size_bytes,
            "filename": result.filename,
        }

    except Exception as exc:
        logger.error(f"Failed to upload to LabArchives: {exc}", exc_info=True)
        raise


async def write_notebook_entry(
    context: ToolContext,
    notebook_id: str,
    content: str,
    page_id: str | None = None,
    page_title: str | None = None,
    parent_folder_id: str | None = None,
    content_format: str = "markdown",
    caption: str | None = None,
    change_description: str | None = None,
) -> dict[str, Any]:
    """Write a rich text entry directly to a LabArchives page."""
    logger.info(
        "write_notebook_entry called: notebook=%s, page_id=%s, title=%s",
        notebook_id,
        page_id,
        page_title,
    )

    try:
        uid = await context.auth_manager.ensure_uid()

        if not content.strip():
            raise ValueError("content cannot be empty")

        if page_id:
            page_tree_id = page_id
        else:
            if not page_title:
                raise ValueError("page_title is required when page_id is not provided")
            page_request = PageCreationRequest(
                notebook_id=notebook_id,
                parent_tree_id=parent_folder_id or 0,
                display_text=page_title,
                is_folder=False,
            )
            page_result = await context.notebook_client.insert_node(uid, page_request)
            page_tree_id = page_result.tree_id

        normalized_format = content_format.strip().lower()
        if normalized_format in {"markdown", "md"}:
            entry_body = context.notebook_client._markdown_to_html(content)
            part_type = "text entry"
        elif normalized_format in {"html", "rich", "rich_text"}:
            entry_body = content
            part_type = "text entry"
        elif normalized_format in {"plain", "text", "plain_text"}:
            entry_body = content
            part_type = "plain text entry"
        else:
            raise ValueError("content_format must be one of: markdown, html, plain")

        created = await context.notebook_client.add_entry(
            uid=uid,
            notebook_id=notebook_id,
            page_tree_id=page_tree_id,
            part_type=part_type,
            entry_data=entry_body,
            caption=caption,
            change_description=change_description,
        )

        created_at = created.get("created_at")
        if created_at:
            created_at_str = created_at
        else:
            created_at_str = datetime.now(UTC).isoformat()

        page_url = f"https://mynotebook.labarchives.com/share/{notebook_id}/{page_tree_id}"

        return {
            "page_tree_id": page_tree_id,
            "entry_id": created.get("eid"),
            "page_url": page_url,
            "created_at": created_at_str,
            "part_type": created.get("part_type", part_type),
        }
    except Exception as exc:
        logger.error(f"Failed to write notebook entry: {exc}", exc_info=True)
        raise


_upload_to_labarchives = upload_to_labarchives
_write_notebook_entry = write_notebook_entry


def register_write_tools(server: Any, context: ToolContext, *, upload_enabled: bool) -> None:
    """Register LabArchives write tools when uploads are enabled."""
    if not upload_enabled:
        logger.info("Upload functionality is DISABLED (LABARCHIVES_ENABLE_UPLOAD=false)")
        return

    logger.info("Upload functionality is ENABLED (LABARCHIVES_ENABLE_UPLOAD)")

    @tool(server)
    async def upload_to_labarchives(
        notebook_id: str,
        page_title: str,
        file_path: str,
        git_commit_sha: str,
        git_branch: str,
        git_repo_url: str,
        python_version: str,
        executed_at: str,
        parent_folder_id: str | None = None,
        caption: str | None = None,
        git_is_dirty: bool = False,
        allow_dirty_git: bool = False,
        dependencies: dict[str, str] | None = None,
        as_page_text: bool = True,
    ) -> dict[str, Any]:
        """Upload a file to LabArchives with code provenance metadata."""
        return await _upload_to_labarchives(
            context,
            notebook_id,
            page_title,
            file_path,
            git_commit_sha,
            git_branch,
            git_repo_url,
            python_version,
            executed_at,
            parent_folder_id=parent_folder_id,
            caption=caption,
            git_is_dirty=git_is_dirty,
            allow_dirty_git=allow_dirty_git,
            dependencies=dependencies,
            as_page_text=as_page_text,
        )

    @tool(server)
    async def write_notebook_entry(
        notebook_id: str,
        content: str,
        page_id: str | None = None,
        page_title: str | None = None,
        parent_folder_id: str | None = None,
        content_format: str = "markdown",
        caption: str | None = None,
        change_description: str | None = None,
    ) -> dict[str, Any]:
        """Write a rich text entry directly to a LabArchives page."""
        return await _write_notebook_entry(
            context,
            notebook_id,
            content,
            page_id=page_id,
            page_title=page_title,
            parent_folder_id=parent_folder_id,
            content_format=content_format,
            caption=caption,
            change_description=change_description,
        )
