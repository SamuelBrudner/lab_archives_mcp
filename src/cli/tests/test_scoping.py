"""
LabArchives MCP Server - FolderPath Scoping Unit Tests

This module provides comprehensive pytest unit tests for the FolderPath value object
that validates exact path comparison logic, string parsing, tuple normalization, and 
immutability. Essential for ensuring the folder scope enforcement system works correctly
and prevents path matching vulnerabilities.

Test Coverage:
- FolderPath.from_raw() factory method validation for string path parsing
- FolderPath.is_parent_of() exact tuple prefix matching logic
- Immutability enforcement using @dataclass(frozen=True, slots=True)
- Edge case handling for empty paths, trailing slashes, and root paths
- Path normalization and component tuple conversion
- Comprehensive validation of all FolderPath methods and properties

Security Critical Tests:
- Ensures 'Chem' is NOT a parent of 'Chemistry' (prevents substring vulnerabilities)
- Validates exact hierarchical path comparison using tuple prefix matching
- Tests path traversal protection and component validation
- Verifies consistent handling of path edge cases

This test suite supports the core security objective of enforcing strict folder-scoped
access control throughout the LabArchives MCP Server with ≥92% test coverage requirement.
"""

import pytest
from dataclasses import FrozenInstanceError, fields
from typing import Optional, List, Tuple, Any

from src.cli.data_models.scoping import FolderPath
from src.cli.exceptions import LabArchivesMCPException
from src.cli.tests.fixtures.config_samples import create_valid_config


class TestFolderPathInitialization:
    """Test suite for FolderPath initialization and validation."""
    
    def test_valid_components_tuple_initialization(self):
        """Test successful FolderPath creation with valid component tuples."""
        # Valid single component
        path = FolderPath(("Projects",))
        assert path.components == ("Projects",)
        
        # Valid multiple components
        path = FolderPath(("Projects", "AI", "Research"))
        assert path.components == ("Projects", "AI", "Research")
        
        # Valid empty tuple (root path)
        path = FolderPath(())
        assert path.components == ()
        assert path.is_root is True
    
    def test_invalid_component_type_raises_exception(self):
        """Test that non-string components raise LabArchivesMCPException."""
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath((123, "Projects"))
        
        assert "Invalid path component type" in str(exc_info.value)
        assert "All components must be strings" in str(exc_info.value)
        assert exc_info.value.code == 400
    
    def test_path_traversal_components_raise_exception(self):
        """Test that path traversal patterns in components raise exceptions."""
        # Test dot component
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath(("Projects", ".", "AI"))
        
        assert "Invalid path component: '.'" in str(exc_info.value)
        assert "Path traversal patterns are not allowed" in str(exc_info.value)
        assert exc_info.value.code == 400
        
        # Test double dot component
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath(("Projects", "..", "AI"))
        
        assert "Invalid path component: '..'" in str(exc_info.value)
        assert "Path traversal patterns are not allowed" in str(exc_info.value)
        assert exc_info.value.code == 400
    
    def test_empty_string_components_raise_exception(self):
        """Test that empty string components in non-root paths raise exceptions."""
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath(("Projects", "", "AI"))
        
        assert "Empty path components are not allowed" in str(exc_info.value)
        assert exc_info.value.code == 400
    
    def test_immutability_with_frozen_dataclass(self):
        """Test that FolderPath instances are immutable (frozen=True)."""
        path = FolderPath(("Projects", "AI"))
        
        # Attempting to modify _components should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            path._components = ("Modified", "Path")
        
        # Verify dataclass is configured with frozen=True and slots=True
        dataclass_fields = fields(FolderPath)
        assert len(dataclass_fields) == 1
        assert dataclass_fields[0].name == "_components"
        
        # Verify the dataclass decorator configuration
        assert path.__dataclass_params__.frozen is True
        assert hasattr(path, "__slots__")


class TestFolderPathFromRaw:
    """Test suite for FolderPath.from_raw() factory method."""
    
    @pytest.mark.parametrize("raw_path,expected_components", [
        # Basic path parsing
        ("Projects", ("Projects",)),
        ("Projects/AI", ("Projects", "AI")),
        ("Projects/AI/Research", ("Projects", "AI", "Research")),
        
        # Root path variations
        ("", ()),
        ("/", ()),
        ("///", ()),
        
        # Leading/trailing slash handling
        ("/Projects", ("Projects",)),
        ("Projects/", ("Projects",)),
        ("/Projects/", ("Projects",)),
        ("/Projects/AI/", ("Projects", "AI")),
        
        # Multiple consecutive slashes
        ("Projects//AI", ("Projects", "AI")),
        ("Projects///AI//Research", ("Projects", "AI", "Research")),
        
        # Whitespace handling
        ("  Projects  ", ("Projects",)),
        ("Projects / AI ", ("Projects", "AI")),
        (" Projects / AI / Research ", ("Projects", "AI", "Research")),
        
        # Combined edge cases
        ("  /Projects// AI /Research/  ", ("Projects", "AI", "Research")),
    ])
    def test_valid_path_parsing(self, raw_path: str, expected_components: Tuple[str, ...]):
        """Test that valid raw paths are parsed correctly into component tuples."""
        path = FolderPath.from_raw(raw_path)
        assert path.components == expected_components
    
    def test_non_string_input_raises_exception(self):
        """Test that non-string inputs raise LabArchivesMCPException."""
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath.from_raw(123)
        
        assert "Invalid path type" in str(exc_info.value)
        assert "Path must be a string" in str(exc_info.value)
        assert exc_info.value.code == 400
    
    def test_path_with_path_traversal_patterns(self):
        """Test that paths containing path traversal patterns are rejected."""
        # Test dot pattern
        with pytest.raises(LabArchivesMCPException):
            FolderPath.from_raw("Projects/./AI")
        
        # Test double dot pattern
        with pytest.raises(LabArchivesMCPException):
            FolderPath.from_raw("Projects/../AI")
        
        # Test combined patterns
        with pytest.raises(LabArchivesMCPException):
            FolderPath.from_raw("Projects/./Research/../AI")
    
    def test_normalization_preserves_valid_components(self):
        """Test that path normalization preserves valid path components."""
        # Test that normalization doesn't affect valid components
        path = FolderPath.from_raw("Projects/AI-Research/Deep_Learning")
        assert path.components == ("Projects", "AI-Research", "Deep_Learning")
        
        # Test with special characters in component names
        path = FolderPath.from_raw("Chemistry/Organic_Chemistry/Lab-Results")
        assert path.components == ("Chemistry", "Organic_Chemistry", "Lab-Results")
    
    def test_empty_components_after_normalization(self):
        """Test handling of empty components after normalization."""
        # Multiple consecutive slashes should be normalized to single components
        path = FolderPath.from_raw("Projects////AI////Research")
        assert path.components == ("Projects", "AI", "Research")
        
        # Leading and trailing slashes with empty components
        path = FolderPath.from_raw("///Projects///AI///")
        assert path.components == ("Projects", "AI")


class TestFolderPathIsParentOf:
    """Test suite for FolderPath.is_parent_of() method."""
    
    def test_valid_parent_child_relationships(self):
        """Test that valid parent-child relationships are correctly identified."""
        # Basic parent-child relationship
        parent = FolderPath.from_raw("Projects")
        child = FolderPath.from_raw("Projects/AI")
        assert parent.is_parent_of(child) is True
        
        # Multi-level parent-child relationship
        parent = FolderPath.from_raw("Projects/AI")
        child = FolderPath.from_raw("Projects/AI/Research/Data")
        assert parent.is_parent_of(child) is True
        
        # Root is parent of all non-root paths
        root = FolderPath.from_raw("")
        any_path = FolderPath.from_raw("Projects/AI/Research")
        assert root.is_parent_of(any_path) is True
    
    def test_invalid_parent_child_relationships(self):
        """Test that invalid parent-child relationships are correctly rejected."""
        # Same path is not parent of itself
        path = FolderPath.from_raw("Projects/AI")
        assert path.is_parent_of(path) is False
        
        # Child is not parent of parent
        parent = FolderPath.from_raw("Projects")
        child = FolderPath.from_raw("Projects/AI")
        assert child.is_parent_of(parent) is False
        
        # Sibling paths are not parent-child
        sibling1 = FolderPath.from_raw("Projects/AI")
        sibling2 = FolderPath.from_raw("Projects/Chemistry")
        assert sibling1.is_parent_of(sibling2) is False
        assert sibling2.is_parent_of(sibling1) is False
        
        # Unrelated paths are not parent-child
        path1 = FolderPath.from_raw("Projects/AI")
        path2 = FolderPath.from_raw("Research/Biology")
        assert path1.is_parent_of(path2) is False
        assert path2.is_parent_of(path1) is False
    
    def test_substring_vulnerability_prevention(self):
        """Test that substring matching vulnerabilities are prevented."""
        # CRITICAL: 'Chem' should NOT be parent of 'Chemistry'
        # This test validates the core security requirement from Section 0.1.2 G-2
        chem_path = FolderPath.from_raw("Chem")
        chemistry_path = FolderPath.from_raw("Chemistry")
        assert chem_path.is_parent_of(chemistry_path) is False
        
        # Additional substring vulnerability tests
        math_path = FolderPath.from_raw("Math")
        mathematics_path = FolderPath.from_raw("Mathematics")
        assert math_path.is_parent_of(mathematics_path) is False
        
        # Test with similar prefixes at different levels
        proj_path = FolderPath.from_raw("Projects/AI")
        proj_ai_ml_path = FolderPath.from_raw("Projects/AI-ML/Research")
        assert proj_path.is_parent_of(proj_ai_ml_path) is False
        
        # Test partial component matches
        research_path = FolderPath.from_raw("Research")
        research_data_path = FolderPath.from_raw("Research-Data")
        assert research_path.is_parent_of(research_data_path) is False
    
    def test_exact_tuple_prefix_matching(self):
        """Test that exact tuple prefix matching is used for comparison."""
        # Test that only exact component matches are considered
        parent = FolderPath.from_raw("Projects/AI")
        
        # Valid child (exact prefix match)
        valid_child = FolderPath.from_raw("Projects/AI/Research")
        assert parent.is_parent_of(valid_child) is True
        
        # Invalid child (partial component match)
        invalid_child = FolderPath.from_raw("Projects/AI-Research")
        assert parent.is_parent_of(invalid_child) is False
        
        # Test multi-level exact matching
        deep_parent = FolderPath.from_raw("Projects/AI/Research")
        deep_child = FolderPath.from_raw("Projects/AI/Research/Data/2024")
        assert deep_parent.is_parent_of(deep_child) is True
    
    def test_root_path_special_cases(self):
        """Test special cases involving root paths."""
        root = FolderPath.from_raw("")
        
        # Root is parent of all non-root paths
        assert root.is_parent_of(FolderPath.from_raw("Projects")) is True
        assert root.is_parent_of(FolderPath.from_raw("Projects/AI/Research")) is True
        
        # Root is not parent of itself
        assert root.is_parent_of(root) is False
        
        # Non-root paths are not parent of root
        non_root = FolderPath.from_raw("Projects")
        assert non_root.is_parent_of(root) is False
    
    def test_invalid_comparison_type_raises_exception(self):
        """Test that comparing with non-FolderPath objects raises exception."""
        path = FolderPath.from_raw("Projects/AI")
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            path.is_parent_of("Projects/AI/Research")
        
        assert "Invalid comparison type" in str(exc_info.value)
        assert "Can only compare with FolderPath instances" in str(exc_info.value)
        assert exc_info.value.code == 400
    
    @pytest.mark.parametrize("parent_path,child_path,expected_result", [
        # Basic parent-child cases
        ("Projects", "Projects/AI", True),
        ("Projects/AI", "Projects/AI/Research", True),
        ("", "Projects", True),  # Root is parent of all
        
        # Non-parent cases
        ("Projects", "Projects", False),  # Same path
        ("Projects/AI", "Projects", False),  # Child cannot be parent
        ("Projects/AI", "Projects/Chemistry", False),  # Siblings
        ("Mathematics", "Math", False),  # Reverse substring
        
        # Critical security test cases
        ("Chem", "Chemistry", False),  # Substring vulnerability
        ("Math", "Mathematics", False),  # Substring vulnerability
        ("Bio", "Biology", False),  # Substring vulnerability
    ])
    def test_is_parent_of_comprehensive(self, parent_path: str, child_path: str, expected_result: bool):
        """Comprehensive parameterized test for is_parent_of method."""
        parent = FolderPath.from_raw(parent_path)
        child = FolderPath.from_raw(child_path)
        assert parent.is_parent_of(child) is expected_result


class TestFolderPathProperties:
    """Test suite for FolderPath properties and methods."""
    
    def test_components_property(self):
        """Test the components property returns correct tuple."""
        # Test with multiple components
        path = FolderPath.from_raw("Projects/AI/Research")
        components = path.components
        assert components == ("Projects", "AI", "Research")
        assert isinstance(components, tuple)
        
        # Test with root path
        root = FolderPath.from_raw("")
        assert root.components == ()
        
        # Test immutability of returned tuple
        # Since tuples are immutable, this ensures the property is safe
        assert type(components) is tuple
    
    def test_is_root_property(self):
        """Test the is_root property correctly identifies root paths."""
        # Root path variations should all be root
        assert FolderPath.from_raw("").is_root is True
        assert FolderPath.from_raw("/").is_root is True
        assert FolderPath.from_raw("///").is_root is True
        
        # Non-root paths should not be root
        assert FolderPath.from_raw("Projects").is_root is False
        assert FolderPath.from_raw("Projects/AI").is_root is False
        assert FolderPath.from_raw("/Projects/AI/").is_root is False
    
    def test_depth_property(self):
        """Test the depth property returns correct component count."""
        # Root path has depth 0
        assert FolderPath.from_raw("").depth == 0
        
        # Single component has depth 1
        assert FolderPath.from_raw("Projects").depth == 1
        
        # Multiple components have correct depth
        assert FolderPath.from_raw("Projects/AI").depth == 2
        assert FolderPath.from_raw("Projects/AI/Research").depth == 3
        assert FolderPath.from_raw("Projects/AI/Research/Data/2024").depth == 5
    
    def test_str_representation(self):
        """Test string representation of FolderPath instances."""
        # Root path string representation
        root = FolderPath.from_raw("")
        assert str(root) == ""
        
        # Single component string representation
        single = FolderPath.from_raw("Projects")
        assert str(single) == "Projects"
        
        # Multi-component string representation
        multi = FolderPath.from_raw("Projects/AI/Research")
        assert str(multi) == "Projects/AI/Research"
        
        # Verify normalization is preserved in string representation
        normalized = FolderPath.from_raw("/Projects//AI/Research/")
        assert str(normalized) == "Projects/AI/Research"
    
    def test_repr_representation(self):
        """Test repr representation shows internal components."""
        # Root path repr
        root = FolderPath.from_raw("")
        assert repr(root) == "FolderPath(_components=())"
        
        # Single component repr
        single = FolderPath.from_raw("Projects")
        assert repr(single) == "FolderPath(_components=('Projects',))"
        
        # Multi-component repr
        multi = FolderPath.from_raw("Projects/AI/Research")
        assert repr(multi) == "FolderPath(_components=('Projects', 'AI', 'Research'))"
    
    def test_equality_comparison(self):
        """Test equality comparison between FolderPath instances."""
        # Same path should be equal
        path1 = FolderPath.from_raw("Projects/AI")
        path2 = FolderPath.from_raw("Projects/AI")
        assert path1 == path2
        
        # Different paths should not be equal
        path3 = FolderPath.from_raw("Projects/Chemistry")
        assert path1 != path3
        
        # Normalized paths should be equal
        path4 = FolderPath.from_raw("/Projects//AI/")
        assert path1 == path4
        
        # Root paths should be equal
        root1 = FolderPath.from_raw("")
        root2 = FolderPath.from_raw("/")
        assert root1 == root2
    
    def test_hash_consistency(self):
        """Test that equal FolderPath instances have consistent hashes."""
        # Same path should have same hash
        path1 = FolderPath.from_raw("Projects/AI")
        path2 = FolderPath.from_raw("Projects/AI")
        assert hash(path1) == hash(path2)
        
        # Normalized paths should have same hash
        path3 = FolderPath.from_raw("/Projects//AI/")
        assert hash(path1) == hash(path3)
        
        # Different paths should have different hashes (usually)
        path4 = FolderPath.from_raw("Projects/Chemistry")
        assert hash(path1) != hash(path4)


class TestFolderPathEdgeCases:
    """Test suite for FolderPath edge cases and error conditions."""
    
    def test_extremely_long_paths(self):
        """Test handling of extremely long paths."""
        # Create a path with many components
        long_components = [f"Level{i}" for i in range(100)]
        long_path_str = "/".join(long_components)
        
        path = FolderPath.from_raw(long_path_str)
        assert path.depth == 100
        assert path.components == tuple(long_components)
        
        # Test parent-child with long paths
        parent_components = long_components[:50]
        parent_path_str = "/".join(parent_components)
        parent = FolderPath.from_raw(parent_path_str)
        
        assert parent.is_parent_of(path) is True
    
    def test_special_characters_in_components(self):
        """Test handling of special characters in path components."""
        # Test with hyphens, underscores, and numbers
        path = FolderPath.from_raw("Project-2024/AI_Research/Data-Set_1")
        assert path.components == ("Project-2024", "AI_Research", "Data-Set_1")
        
        # Test with spaces in components (after normalization)
        path = FolderPath.from_raw("My Projects/AI Research/Data Analysis")
        assert path.components == ("My Projects", "AI Research", "Data Analysis")
    
    def test_unicode_characters_in_components(self):
        """Test handling of unicode characters in path components."""
        # Test with unicode characters
        path = FolderPath.from_raw("项目/人工智能/研究")
        assert path.components == ("项目", "人工智能", "研究")
        
        # Test mixed ASCII and unicode
        path = FolderPath.from_raw("Projects/AI-研究/Data")
        assert path.components == ("Projects", "AI-研究", "Data")
    
    def test_case_sensitivity(self):
        """Test that path comparison is case-sensitive."""
        path1 = FolderPath.from_raw("Projects/AI")
        path2 = FolderPath.from_raw("projects/ai")
        path3 = FolderPath.from_raw("Projects/ai")
        
        # Should not be equal due to case sensitivity
        assert path1 != path2
        assert path1 != path3
        
        # Should not be parent-child due to case sensitivity
        assert path1.is_parent_of(path2) is False
        assert path2.is_parent_of(path1) is False
    
    def test_whitespace_only_components_handling(self):
        """Test handling of whitespace-only components."""
        # Whitespace-only components should be normalized away
        path = FolderPath.from_raw("Projects/   /AI")
        # The middle component should be filtered out during normalization
        assert path.components == ("Projects", "AI")
        
        # Test with tabs and other whitespace
        path = FolderPath.from_raw("Projects/\t\n/AI")
        assert path.components == ("Projects", "AI")


class TestFolderPathIntegration:
    """Integration tests for FolderPath with other system components."""
    
    def test_folder_path_with_valid_config(self):
        """Test FolderPath integration with valid configuration."""
        config = create_valid_config()
        
        # Test that FolderPath can be used with configuration scope
        if config.scope.folder_path:
            folder_path = FolderPath.from_raw(config.scope.folder_path)
            assert isinstance(folder_path, FolderPath)
            assert folder_path.components is not None
    
    def test_folder_path_error_context(self):
        """Test that FolderPath exceptions provide useful context."""
        try:
            FolderPath.from_raw(123)
        except LabArchivesMCPException as e:
            assert e.code == 400
            assert e.context is not None
            assert "path" in e.context
            assert "path_type" in e.context
    
    def test_folder_path_thread_safety(self):
        """Test that FolderPath instances are thread-safe."""
        # Create a FolderPath instance
        path = FolderPath.from_raw("Projects/AI/Research")
        
        # Verify immutability guarantees thread safety
        with pytest.raises(FrozenInstanceError):
            path._components = ("Modified", "Components")
        
        # Verify that all operations are read-only
        original_components = path.components
        path.is_parent_of(FolderPath.from_raw("Projects"))
        path.is_root
        path.depth
        str(path)
        repr(path)
        
        # Components should remain unchanged
        assert path.components == original_components
    
    def test_folder_path_memory_efficiency(self):
        """Test that FolderPath uses slots for memory efficiency."""
        path = FolderPath.from_raw("Projects/AI/Research")
        
        # Verify that the dataclass is configured with slots=True
        # This is confirmed by checking the dataclass parameters
        assert path.__dataclass_params__.slots is True
        
        # Verify that the dataclass is configured with frozen=True for immutability
        assert path.__dataclass_params__.frozen is True
        
        # Test that the class uses slots by checking it doesn't have __dict__
        # (slots prevents __dict__ from being created for memory efficiency)
        assert not hasattr(path, '__dict__')
        
        # Verify that only the defined field exists
        from dataclasses import fields
        field_names = {field.name for field in fields(path)}
        assert field_names == {"_components"}
        
        # Memory efficiency is ensured by the combination of slots=True and frozen=True
        # which prevents instance dictionary creation and attribute modification


class TestFolderPathPerformance:
    """Performance and stress tests for FolderPath operations."""
    
    def test_large_scale_parent_child_operations(self):
        """Test performance with large-scale parent-child operations."""
        # Create a deep hierarchy
        root = FolderPath.from_raw("")
        paths = []
        
        current_path = ""
        for i in range(20):
            current_path += f"/Level{i}"
            paths.append(FolderPath.from_raw(current_path))
        
        # Test that each level is parent of all deeper levels
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                assert paths[i].is_parent_of(paths[j]) is True
                assert paths[j].is_parent_of(paths[i]) is False
    
    def test_comparison_performance_with_similar_paths(self):
        """Test comparison performance with many similar paths."""
        # Create many similar paths to test comparison efficiency
        base_path = "Projects/AI/Research"
        paths = []
        
        for i in range(100):
            path_str = f"{base_path}/Experiment{i}"
            paths.append(FolderPath.from_raw(path_str))
        
        base = FolderPath.from_raw(base_path)
        
        # Test that base is parent of all experiment paths
        for experiment_path in paths:
            assert base.is_parent_of(experiment_path) is True
        
        # Test that experiment paths are not parents of each other
        for i in range(len(paths)):
            for j in range(len(paths)):
                if i != j:
                    assert paths[i].is_parent_of(paths[j]) is False


class TestFolderPathValidationScenarios:
    """Test scenarios that validate specific requirements from the specification."""
    
    def test_scope_violation_prevention(self):
        """Test that FolderPath prevents scope violations as per security requirements."""
        # Test case from specification: "Chem" must not match "Chemistry"
        chem_folder = FolderPath.from_raw("Chem")
        chemistry_folder = FolderPath.from_raw("Chemistry")
        
        # CRITICAL: This must be False to prevent scope violations
        assert chem_folder.is_parent_of(chemistry_folder) is False
        
        # Additional scope violation tests
        bio_folder = FolderPath.from_raw("Bio")
        biology_folder = FolderPath.from_raw("Biology")
        assert bio_folder.is_parent_of(biology_folder) is False
        
        # Test hierarchical scope violations
        research_folder = FolderPath.from_raw("Research")
        research_data_folder = FolderPath.from_raw("Research-Data")
        assert research_folder.is_parent_of(research_data_folder) is False
    
    def test_exact_hierarchical_path_comparison(self):
        """Test exact hierarchical path comparison using tuple prefix matching."""
        # Test exact component matching
        parent = FolderPath.from_raw("Projects/AI")
        
        # Valid child (exact prefix)
        valid_child = FolderPath.from_raw("Projects/AI/Research")
        assert parent.is_parent_of(valid_child) is True
        
        # Invalid child (partial component match)
        invalid_child = FolderPath.from_raw("Projects/AI-Research")
        assert parent.is_parent_of(invalid_child) is False
        
        # Test with multiple levels
        deep_parent = FolderPath.from_raw("Projects/AI/Research")
        deep_child = FolderPath.from_raw("Projects/AI/Research/Data/2024")
        assert deep_parent.is_parent_of(deep_child) is True
        
        # Test with similar but not exact paths
        similar_parent = FolderPath.from_raw("Projects/AI/Research")
        similar_child = FolderPath.from_raw("Projects/AI/Research-Data")
        assert similar_parent.is_parent_of(similar_child) is False
    
    def test_tuple_prefix_matching_implementation(self):
        """Test that tuple prefix matching is correctly implemented."""
        # Create paths with known component tuples
        parent = FolderPath(("Projects", "AI"))
        child = FolderPath(("Projects", "AI", "Research", "Data"))
        
        # Verify tuple prefix matching
        assert parent.is_parent_of(child) is True
        
        # Test that all parent components match child components
        parent_components = parent.components
        child_components = child.components
        
        # Parent should have fewer components
        assert len(parent_components) < len(child_components)
        
        # All parent components should match corresponding child components
        for i in range(len(parent_components)):
            assert parent_components[i] == child_components[i]
    
    def test_string_vs_tuple_consistency(self):
        """Test consistency between string parsing and tuple operations."""
        # Create same path using string parsing and tuple construction
        string_path = FolderPath.from_raw("Projects/AI/Research")
        tuple_path = FolderPath(("Projects", "AI", "Research"))
        
        # Should be equal
        assert string_path == tuple_path
        assert string_path.components == tuple_path.components
        
        # Should have same behavior
        test_child = FolderPath.from_raw("Projects/AI/Research/Data")
        assert string_path.is_parent_of(test_child) == tuple_path.is_parent_of(test_child)