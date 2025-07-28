"""
LabArchives MCP Server - Folder Path Scoping Models

This module provides immutable value objects for implementing exact hierarchical folder path
comparison using normalized tuple-based representation. The FolderPath class replaces vulnerable
substring-based path matching throughout the resource management system to ensure strict
folder-scoped access control compliance.

Key Features:
- Immutable value object pattern for thread safety and consistent comparison semantics
- Exact tuple prefix matching to eliminate false positives (e.g., 'Chem' vs 'Chemistry')
- Comprehensive edge case handling for trailing slashes, empty components, and root paths
- Normalized path representation for consistent comparison operations
- Integration with LabArchives MCP Server exception hierarchy

This module supports the core security objective of enforcing strict folder-scoped access
control throughout the LabArchives MCP Server, ensuring that once a folder scope is configured,
ALL resource operations (listing and reading) respect that boundary without exceptions.

The FolderPath class is designed to be used by the ResourceManager for implementing
two-phase listing algorithms and scope validation with proper 403 ScopeViolation error
handling for out-of-scope access attempts.
"""

from dataclasses import dataclass
from typing import Tuple

from exceptions import LabArchivesMCPException


@dataclass(frozen=True, slots=True)
class FolderPath:
    """
    Immutable value object implementing exact hierarchical folder path comparison.

    This class provides thread-safe, exact prefix matching using normalized tuple-based
    representation to replace vulnerable substring-based path matching throughout the
    resource management system. The implementation ensures strict folder-scoped access
    control compliance by eliminating false positives like 'Chem' matching 'Chemistry'.

    The FolderPath uses tuple-based internal representation for exact matching operations,
    where each path component is stored as a separate tuple element. This enables precise
    parent-child relationship determination without substring vulnerabilities.

    Key Design Principles:
    - Immutability: Once created, instances cannot be modified (thread-safe)
    - Normalization: All paths are normalized to consistent representation
    - Exact Matching: No substring-based matching, only exact component comparison
    - Edge Case Handling: Robust handling of trailing slashes, empty components, root paths

    Usage:
        # Create FolderPath from string
        folder_path = FolderPath.from_raw("Projects/AI/Research")

        # Check parent-child relationships
        parent = FolderPath.from_raw("Projects/AI")
        child = FolderPath.from_raw("Projects/AI/Research/Data")

        if parent.is_parent_of(child):
            print("Access allowed within scope")
        else:
            print("Access denied - out of scope")

    Thread Safety:
        This class is completely thread-safe due to its immutable design with frozen=True
        and slots=True. Multiple threads can safely access the same FolderPath instance
        without synchronization concerns.
    """

    # Tuple of normalized path components for exact prefix matching
    # Each component is stripped of whitespace and validated for validity
    # Empty string represents root path, empty tuple represents invalid path
    _components: Tuple[str, ...]

    def __post_init__(self):
        """
        Validate the normalized path components after dataclass initialization.

        Ensures that all path components are valid strings without forbidden characters
        and that the overall path structure is consistent. This validation occurs after
        the dataclass __init__ but before the object is frozen.

        Raises:
            LabArchivesMCPException: If any path component contains invalid characters
                                   or if the path structure is malformed
        """
        # Validate each component for invalid characters that could cause security issues
        for component in self._components:
            if not isinstance(component, str):
                raise LabArchivesMCPException(
                    message=f"Invalid path component type: {type(component).__name__}. All components must be strings.",
                    code=400,
                    context={
                        "component": component,
                        "component_type": type(component).__name__,
                    },
                )

            # Check for dangerous path traversal patterns
            if component in (".", ".."):
                raise LabArchivesMCPException(
                    message=f"Invalid path component: '{component}'. Path traversal patterns are not allowed.",
                    code=400,
                    context={"component": component, "pattern": "path_traversal"},
                )

            # Check for empty components (except for root path represented as empty tuple)
            if component == "" and len(self._components) > 0:
                raise LabArchivesMCPException(
                    message="Empty path components are not allowed in non-root paths.",
                    code=400,
                    context={"components": self._components},
                )

    @classmethod
    def from_raw(cls, raw_path: str) -> "FolderPath":
        """
        Create a FolderPath instance from a raw string path with normalization.

        This factory method parses string paths into normalized component tuples,
        handling edge cases like trailing slashes, empty components, and root paths
        consistently. The normalization process ensures that equivalent paths have
        identical internal representations for accurate comparison.

        Normalization Process:
        1. Strip leading and trailing whitespace from the entire path
        2. Remove leading and trailing forward slashes
        3. Split path into components using forward slash as delimiter
        4. Strip whitespace from each component
        5. Filter out empty components (except for root path)
        6. Validate each component for security and consistency

        Args:
            raw_path (str): Raw folder path string to be normalized and parsed.
                          Examples: "Projects/AI/Research", "/Projects/AI/", "Projects//AI"

        Returns:
            FolderPath: Immutable FolderPath instance with normalized components.
                       Root path returns FolderPath with empty tuple.
                       Valid paths return FolderPath with tuple of component strings.

        Raises:
            LabArchivesMCPException: If the raw path is invalid, contains illegal characters,
                                   or cannot be normalized to a valid folder path.

        Examples:
            >>> FolderPath.from_raw("Projects/AI/Research")
            FolderPath(_components=('Projects', 'AI', 'Research'))

            >>> FolderPath.from_raw("/Projects/AI/")
            FolderPath(_components=('Projects', 'AI'))

            >>> FolderPath.from_raw("")
            FolderPath(_components=())

            >>> FolderPath.from_raw("Projects//AI")
            FolderPath(_components=('Projects', 'AI'))
        """
        # Validate input parameter
        if not isinstance(raw_path, str):
            raise LabArchivesMCPException(
                message=f"Invalid path type: {type(raw_path).__name__}. Path must be a string.",
                code=400,
                context={"path": raw_path, "path_type": type(raw_path).__name__},
            )

        # Step 1: Strip leading and trailing whitespace
        normalized_path = raw_path.strip()

        # Step 2: Handle root path and empty path cases
        if normalized_path == "" or normalized_path == "/":
            return cls(_components=())

        # Step 3: Remove leading and trailing slashes
        normalized_path = normalized_path.strip("/")

        # Step 4: Split path into components and normalize each
        if normalized_path == "":
            # After stripping slashes, if empty, it's root path
            components = ()
        else:
            # Split by forward slash and process each component
            raw_components = normalized_path.split("/")
            components = []

            for component in raw_components:
                # Strip whitespace from component
                normalized_component = component.strip()

                # Skip empty components (from multiple consecutive slashes)
                if normalized_component != "":
                    components.append(normalized_component)

            # Convert to tuple for immutability
            components = tuple(components)

        # Step 5: Create and return FolderPath instance
        # The __post_init__ method will validate the components
        try:
            return cls(_components=components)
        except Exception as e:
            # Re-raise any validation errors with additional context
            if isinstance(e, LabArchivesMCPException):
                raise e
            else:
                raise LabArchivesMCPException(
                    message=f"Failed to create FolderPath from raw path: {str(e)}",
                    code=400,
                    context={
                        "raw_path": raw_path,
                        "normalized_path": normalized_path,
                        "error": str(e),
                    },
                )

    def is_parent_of(self, other: "FolderPath") -> bool:
        """
        Determine if this FolderPath is a parent of another FolderPath using exact prefix matching.

        This method implements exact tuple prefix matching to replace vulnerable substring-based
        path matching throughout the resource management system. The comparison ensures that
        'Chem' does not match 'Chemistry' by comparing complete path components rather than
        substring patterns.

        Parent-Child Relationship Rules:
        1. A path is a parent of another if it's a proper prefix of the other path's components
        2. Root path (empty components) is parent of all non-root paths
        3. A path is NOT a parent of itself (strict parent relationship)
        4. Empty path components are handled consistently
        5. Comparison is case-sensitive and exact

        Algorithm:
        1. Check if this path has fewer components than the other path (necessary for parent)
        2. Compare each component of this path with corresponding component of other path
        3. Return True only if all components match exactly and other path has more components

        Args:
            other (FolderPath): The potential child FolderPath to compare against.
                              Must be a valid FolderPath instance.

        Returns:
            bool: True if this FolderPath is a parent of the other FolderPath.
                  False if they are equal, unrelated, or if other is parent of this.

        Raises:
            LabArchivesMCPException: If the other parameter is not a FolderPath instance
                                   or if comparison cannot be performed.

        Examples:
            >>> parent = FolderPath.from_raw("Projects/AI")
            >>> child = FolderPath.from_raw("Projects/AI/Research")
            >>> parent.is_parent_of(child)
            True

            >>> folder1 = FolderPath.from_raw("Chem")
            >>> folder2 = FolderPath.from_raw("Chemistry")
            >>> folder1.is_parent_of(folder2)
            False

            >>> root = FolderPath.from_raw("")
            >>> any_folder = FolderPath.from_raw("Projects")
            >>> root.is_parent_of(any_folder)
            True

            >>> same = FolderPath.from_raw("Projects/AI")
            >>> same.is_parent_of(same)
            False
        """
        # Validate input parameter
        if not isinstance(other, FolderPath):
            raise LabArchivesMCPException(
                message=f"Invalid comparison type: {type(other).__name__}. Can only compare with FolderPath instances.",
                code=400,
                context={"other_type": type(other).__name__},
            )

        # Rule 1: Parent must have fewer components than child (strict parent relationship)
        if len(self._components) >= len(other._components):
            return False

        # Rule 2: All components of parent must match corresponding components of child
        for i in range(len(self._components)):
            if self._components[i] != other._components[i]:
                return False

        # Rule 3: If we reach here, this path is a proper prefix of the other path
        return True

    def __str__(self) -> str:
        """
        Return a human-readable string representation of the FolderPath.

        Converts the internal tuple representation back to a standardized string format
        for display purposes, logging, and debugging. The string representation uses
        forward slashes as separators and does not include leading or trailing slashes
        (except for root path which is represented as empty string).

        Returns:
            str: String representation of the folder path.
                 Empty string for root path.
                 Forward-slash separated path for non-root paths.

        Examples:
            >>> str(FolderPath.from_raw("Projects/AI/Research"))
            'Projects/AI/Research'

            >>> str(FolderPath.from_raw(""))
            ''

            >>> str(FolderPath.from_raw("/Projects/AI/"))
            'Projects/AI'
        """
        if len(self._components) == 0:
            return ""
        return "/".join(self._components)

    def __repr__(self) -> str:
        """
        Return a detailed string representation for debugging and development.

        Provides the complete internal representation including the tuple components
        for debugging purposes. This representation can be used to understand the
        exact internal state of the FolderPath instance.

        Returns:
            str: Detailed representation showing internal components tuple.

        Examples:
            >>> repr(FolderPath.from_raw("Projects/AI"))
            "FolderPath(_components=('Projects', 'AI'))"

            >>> repr(FolderPath.from_raw(""))
            "FolderPath(_components=())"
        """
        return f"FolderPath(_components={self._components!r})"

    @property
    def components(self) -> Tuple[str, ...]:
        """
        Read-only access to the normalized path components.

        Provides safe access to the internal tuple representation for advanced
        operations while maintaining immutability guarantees. The returned tuple
        is the actual internal representation, but since tuples are immutable,
        this does not compromise the immutability of the FolderPath instance.

        Returns:
            Tuple[str, ...]: Immutable tuple of normalized path components.
                           Empty tuple for root path.
                           Non-empty tuple for valid folder paths.

        Examples:
            >>> path = FolderPath.from_raw("Projects/AI/Research")
            >>> path.components
            ('Projects', 'AI', 'Research')

            >>> root = FolderPath.from_raw("")
            >>> root.components
            ()
        """
        return self._components

    @property
    def is_root(self) -> bool:
        """
        Check if this FolderPath represents the root path.

        A root path is represented by an empty tuple of components and grants
        access to all resources without folder-based restrictions. This property
        is useful for implementing scope validation logic in the ResourceManager.

        Returns:
            bool: True if this is the root path (empty components).
                  False if this is a non-root folder path.

        Examples:
            >>> FolderPath.from_raw("").is_root
            True

            >>> FolderPath.from_raw("Projects").is_root
            False

            >>> FolderPath.from_raw("/").is_root
            True
        """
        return len(self._components) == 0

    @property
    def depth(self) -> int:
        """
        Get the depth of the folder path (number of components).

        Returns the number of path components, which represents the hierarchical
        depth of the folder. Root path has depth 0, first-level folders have
        depth 1, etc. This property is useful for implementing depth-based
        access control and navigation logic.

        Returns:
            int: Number of components in the path.
                 0 for root path.
                 Positive integer for non-root paths.

        Examples:
            >>> FolderPath.from_raw("").depth
            0

            >>> FolderPath.from_raw("Projects").depth
            1

            >>> FolderPath.from_raw("Projects/AI/Research").depth
            3
        """
        return len(self._components)
