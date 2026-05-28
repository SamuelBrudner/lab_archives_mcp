"""Typed response contracts for LabArchives MCP tools."""

from __future__ import annotations

from typing import Literal, NotRequired, Required, TypeAlias, TypedDict

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class NotebookResponse(TypedDict):
    nbid: str
    name: str
    owner: str
    owner_email: str
    owner_name: str
    created_at: str
    modified_at: str


class NotebookPageResponse(TypedDict):
    tree_id: str | None
    title: str | None
    is_page: bool
    is_folder: bool


class NotebookTreeNodeResponse(TypedDict, total=False):
    tree_id: str | None
    display_text: str | None
    name: str | None
    is_page: bool
    is_folder: bool


class PageEntryResponse(TypedDict, total=False):
    eid: str | None
    part_type: str | None
    created_at: str | None
    updated_at: str | None
    content: str | None
    caption: str | None
    filename: str | None


class ReadNotebookPageResponse(TypedDict):
    notebook_id: str
    page_id: str
    entries: list[PageEntryResponse]
    tracked_in_project: str | None
    tracked: bool
    dry_run: bool


class ProjectDraftResponse(TypedDict):
    name: str
    description: str
    linked_notebook_ids: list[str]


ProjectContextResponse: TypeAlias = JsonObject


class CreateProjectOkResponse(TypedDict):
    status: Literal["ok"]
    project: ProjectContextResponse


class CreateProjectDryRunResponse(TypedDict):
    status: Literal["dry_run"]
    project: ProjectDraftResponse


CreateProjectResponse: TypeAlias = CreateProjectOkResponse | CreateProjectDryRunResponse


class DeleteProjectOkResponse(TypedDict):
    status: Literal["ok"]
    project_id: str


class DeleteProjectDryRunResponse(TypedDict):
    status: Literal["dry_run"]
    project_id: str


class DeleteProjectErrorResponse(TypedDict):
    status: Literal["error"]
    code: Literal["project_not_found", "delete_failed"]
    project_id: str


DeleteProjectResponse: TypeAlias = (
    DeleteProjectOkResponse | DeleteProjectDryRunResponse | DeleteProjectErrorResponse
)


class SwitchProjectOkResponse(TypedDict):
    status: Literal["ok"]
    project: ProjectContextResponse


class SwitchProjectDryRunResponse(TypedDict):
    status: Literal["dry_run"]
    project: ProjectContextResponse


class SwitchProjectErrorResponse(TypedDict):
    status: Literal["error"]
    code: Literal["project_not_found", "switch_failed"]
    message: NotRequired[str]
    project_id: NotRequired[str]


SwitchProjectResponse: TypeAlias = (
    SwitchProjectOkResponse | SwitchProjectDryRunResponse | SwitchProjectErrorResponse
)


class ProjectSummaryResponse(TypedDict):
    id: str
    name: str
    status: str
    active: bool


class LogFindingOkResponse(TypedDict):
    status: Literal["ok"]
    content: str
    project: str
    project_id: str | None


class LogFindingDryRunResponse(TypedDict):
    status: Literal["dry_run"]
    content: str
    page_id: str | None


class LogFindingErrorResponse(TypedDict):
    status: Literal["error"]
    code: Literal["no_active_context"]
    message: str


LogFindingResponse: TypeAlias = (
    LogFindingOkResponse | LogFindingDryRunResponse | LogFindingErrorResponse
)


class NoActiveContextResponse(TypedDict):
    status: Literal["no_active_context"]
    message: str


CurrentContextResponse: TypeAlias = ProjectContextResponse | NoActiveContextResponse


class PaginationMetaResponse(TypedDict):
    total: int
    offset: int
    limit: int | None
    truncated: bool


class RelatedPageResponse(TypedDict):
    page_id: str
    title: str
    source: str


class RelatedPagesResponse(TypedDict):
    items: list[RelatedPageResponse]
    meta: PaginationMetaResponse


class ProvenanceSourceResponse(TypedDict):
    id: str
    type: str
    description: str


class TraceProvenanceFoundResponse(TypedDict):
    sources: list[ProvenanceSourceResponse]
    metadata: JsonObject


class TraceProvenanceMissingResponse(TypedDict):
    error: str


TraceProvenanceResponse: TypeAlias = TraceProvenanceFoundResponse | TraceProvenanceMissingResponse


class SuggestionStatsResponse(TypedDict):
    pages_visited: int
    findings_logged: int
    project_name: str


class SuggestNextStepsResponse(TypedDict, total=False):
    phase: Required[Literal["no_context", "cold_start", "active"]]
    suggestions: Required[list[str]]
    stats: SuggestionStatsResponse


class SearchResultResponse(TypedDict):
    score: float
    notebook_name: str
    page_title: str
    page_id: str
    notebook_id: str
    url: str
    author: str
    date: str
    content: str


class SyncVectorIndexResponse(TypedDict, total=False):
    action: Required[str]
    reason: Required[str]
    built_at: Required[str | None]
    dry_run: bool
    processed_pages: int
    indexed_chunks: int


class UploadToLabArchivesResponse(TypedDict):
    page_tree_id: str
    entry_id: str | None
    page_url: str
    created_at: str
    file_size_bytes: int
    filename: str


class WriteNotebookEntryResponse(TypedDict):
    page_tree_id: str
    entry_id: str | None
    page_url: str
    created_at: str
    part_type: str


class LabArchivesErrorResponse(TypedDict):
    code: str
    message: str
    retryable: bool
    domain: Literal["labarchives"]


class NotebooksResourceResponse(TypedDict, total=False):
    resource: Required[Literal["labarchives://notebooks"]]
    list: list[NotebookResponse]
    error: LabArchivesErrorResponse


OnboardPayloadResponse: TypeAlias = JsonObject
ProvenanceJsonLdResponse: TypeAlias = JsonObject
