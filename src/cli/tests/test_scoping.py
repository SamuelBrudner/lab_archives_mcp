"""
Comprehensive unit tests for src/cli/models/scoping.py

This test module validates the FolderPath value object that implements exact hierarchical
folder path comparison using normalized tuple-based representation. The tests ensure
strict folder-scoped access control compliance and verify that all requirements from
the summary of changes are properly implemented.

Key Testing Areas:
- Immutable value object implementation (@dataclass(frozen=True, slots=True))
- String path parsing and normalization (from_raw() method)
- Exact tuple prefix matching (is_parent_of() method)
- Edge case handling (trailing slashes, empty components, root paths)
- Error handling and exception integration
- Thread safety through immutability
- G-2 Success Metric: 'Chem' must not match 'Chemistry'
"""

import pytest
from typing import Optional, List, Tuple, Any
from dataclasses import FrozenInstanceError

from src.cli.models.scoping import FolderPath
from src.cli.exceptions import LabArchivesMCPException


class TestFolderPathCreation:
    """Test FolderPath creation and basic properties."""
    
    def test_from_raw_basic_paths(self):
        """Test basic path creation from raw strings."""
        test_cases = [
            ("Projects/AI/Research", ("Projects", "AI", "Research")),
            ("Projects", ("Projects",)),
            ("", ()),
            ("/", ()),
            ("Projects/AI", ("Projects", "AI")),
        ]
        
        for raw_path, expected_components in test_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected_components
            
    def test_from_raw_normalization(self):
        """Test path normalization during creation."""
        normalization_cases = [
            # (input, expected_components, description)
            ("/Projects/AI/", ("Projects", "AI"), "leading and trailing slashes"),
            ("Projects//AI", ("Projects", "AI"), "double slashes"),
            ("  Projects/AI  ", ("Projects", "AI"), "surrounding whitespace"),
            ("Projects///AI", ("Projects", "AI"), "triple slashes"),
            ("//Projects//AI//", ("Projects", "AI"), "multiple slashes everywhere"),
            ("Projects/ /AI", ("Projects", "AI"), "whitespace component"),
        ]
        
        for raw_path, expected_components, description in normalization_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected_components, f"Failed normalization: {description}"
            
    def test_from_raw_root_paths(self):
        """Test various root path representations."""
        root_cases = ["", "/", "  ", " / ", "///", "   /   "]
        
        for root_path in root_cases:
            folder_path = FolderPath.from_raw(root_path)
            assert folder_path.is_root, f"'{root_path}' should be root"
            assert folder_path.components == (), f"Root path should have empty components"
            
    def test_from_raw_invalid_paths(self):
        """Test that invalid paths raise appropriate exceptions."""
        invalid_cases = [
            ("Projects/../AI", "path traversal with parent directory"),
            ("Projects/./AI", "path traversal with current directory"),
            ("Projects/..", "parent directory component"),
            ("Projects/.", "current directory component"),
        ]
        
        for invalid_path, description in invalid_cases:
            with pytest.raises(LabArchivesMCPException) as exc_info:
                FolderPath.from_raw(invalid_path)
            assert exc_info.value.code == 400, f"Should use code 400 for {description}"
            
    def test_from_raw_edge_case_components(self):
        """Test edge cases that should be allowed."""
        # These cases should be allowed as they're valid component names
        valid_edge_cases = [
            ("Projects/..AI", ("Projects", "..AI")),  # Component starting with dots but not exactly ".."
            ("Projects/AI.", ("Projects", "AI.")),   # Component ending with dot
            ("Projects/.hidden", ("Projects", ".hidden")),  # Hidden file/folder style
        ]
        
        for raw_path, expected_components in valid_edge_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected_components
            
    def test_from_raw_invalid_types(self):
        """Test that non-string inputs raise appropriate exceptions."""
        invalid_types = [123, None, [], {}, 45.67]
        
        for invalid_input in invalid_types:
            with pytest.raises(LabArchivesMCPException) as exc_info:
                FolderPath.from_raw(invalid_input)
            assert exc_info.value.code == 400


class TestFolderPathImmutability:
    """Test FolderPath immutability and dataclass implementation."""
    
    def test_dataclass_properties(self):
        """Test that FolderPath is properly implemented as a dataclass."""
        # Test dataclass attributes
        assert hasattr(FolderPath, '__dataclass_fields__')
        assert hasattr(FolderPath, '__dataclass_params__')
        
        # Test frozen and slots parameters
        params = getattr(FolderPath, '__dataclass_params__')
        assert params.frozen == True, "Should be frozen=True"
        assert params.slots == True, "Should be slots=True"
        
    def test_immutability_enforcement(self):
        """Test that FolderPath instances are immutable."""
        folder_path = FolderPath.from_raw("Projects/AI")
        
        # Test that direct attribute modification fails
        with pytest.raises(FrozenInstanceError):
            folder_path._components = ("Modified",)
            
    def test_slots_implementation(self):
        """Test that slots are properly implemented."""
        folder_path = FolderPath.from_raw("Projects/AI")
        
        # Should not have __dict__ with slots
        assert not hasattr(folder_path, '__dict__')
        
        # Should have __slots__ on the class
        assert hasattr(FolderPath, '__slots__')
        
    def test_thread_safety(self):
        """Test thread safety through immutability."""
        folder_path = FolderPath.from_raw("Projects/AI/Research")
        
        # Multiple access should return identical results
        components1 = folder_path.components
        components2 = folder_path.components
        str1 = str(folder_path)
        str2 = str(folder_path)
        
        assert components1 == components2
        assert str1 == str2
        assert components1 is components2  # Same tuple object


class TestFolderPathComparison:
    """Test FolderPath comparison logic with exact tuple prefix matching."""
    
    def test_g2_success_metric(self):
        """Test G-2 Success Metric: 'Chem' must not match 'Chemistry'."""
        chem = FolderPath.from_raw("Chem")
        chemistry = FolderPath.from_raw("Chemistry")
        
        # Critical test: Chem should NOT be parent of Chemistry
        assert not chem.is_parent_of(chemistry), "G-2 FAILURE: 'Chem' must not match 'Chemistry'"
        
        # Test reverse direction as well
        assert not chemistry.is_parent_of(chem), "Chemistry should not be parent of Chem"
        
    def test_substring_vulnerability_prevention(self):
        """Test that substring-based vulnerabilities are prevented."""
        vulnerability_tests = [
            # (potential_parent, potential_child, should_be_parent)
            ("Lab", "Laboratory", False),
            ("Bio", "Biology", False),
            ("Math", "Mathematics", False),
            ("Phys", "Physics", False),
            ("Chem", "Chemical", False),
            ("AI", "AIResearch", False),  # No slash separator
            
            # These should still work (proper parent-child)
            ("Projects", "Projects/Chemistry", True),
            ("Research/Chem", "Research/Chem/Experiments", True),
            ("Lab/Bio", "Lab/Bio/Samples", True),
        ]
        
        for parent_str, child_str, expected in vulnerability_tests:
            parent = FolderPath.from_raw(parent_str)
            child = FolderPath.from_raw(child_str)
            result = parent.is_parent_of(child)
            assert result == expected, f"Vulnerability test failed: '{parent_str}' -> '{child_str}'"
            
    def test_valid_parent_child_relationships(self):
        """Test valid parent-child relationships."""
        valid_cases = [
            ("Projects", "Projects/AI", True),
            ("Projects/AI", "Projects/AI/Research", True),
            ("", "Projects", True),  # Root is parent of everything
            ("Projects/AI", "Projects/AI/Research/Data", True),
            ("A", "A/B/C/D/E", True),  # Deep nesting
        ]
        
        for parent_str, child_str, expected in valid_cases:
            parent = FolderPath.from_raw(parent_str)
            child = FolderPath.from_raw(child_str)
            result = parent.is_parent_of(child)
            assert result == expected, f"Valid parent test failed: '{parent_str}' -> '{child_str}'"
            
    def test_invalid_parent_child_relationships(self):
        """Test cases that should NOT be parent-child relationships."""
        invalid_cases = [
            ("Projects/AI", "Projects/AI", False),  # Same path
            ("Projects/AI", "Projects", False),  # Child -> Parent
            ("Projects/Data", "Projects/AI", False),  # Siblings
            ("Projects", "Research", False),  # Unrelated
            ("Projects/AI/Research", "Projects/AI", False),  # Child -> Parent
            ("ABC", "DEF", False),  # Completely unrelated
        ]
        
        for parent_str, child_str, expected in invalid_cases:
            parent = FolderPath.from_raw(parent_str)
            child = FolderPath.from_raw(child_str)
            result = parent.is_parent_of(child)
            assert result == expected, f"Invalid parent test failed: '{parent_str}' -> '{child_str}'"
            
    def test_is_parent_of_invalid_types(self):
        """Test that is_parent_of raises exception for invalid types."""
        folder_path = FolderPath.from_raw("Projects")
        
        invalid_types = ["string", 123, None, [], {}]
        
        for invalid_input in invalid_types:
            with pytest.raises(LabArchivesMCPException) as exc_info:
                folder_path.is_parent_of(invalid_input)
            assert exc_info.value.code == 400


class TestFolderPathProperties:
    """Test FolderPath properties and methods."""
    
    def test_components_property(self):
        """Test the components property."""
        test_cases = [
            ("Projects/AI/Research", ("Projects", "AI", "Research")),
            ("Single", ("Single",)),
            ("", ()),
        ]
        
        for raw_path, expected_components in test_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected_components
            assert isinstance(folder_path.components, tuple)
            
    def test_is_root_property(self):
        """Test the is_root property."""
        # Root paths
        root_cases = ["", "/", "  ", " / "]
        for root_path in root_cases:
            folder_path = FolderPath.from_raw(root_path)
            assert folder_path.is_root, f"'{root_path}' should be root"
            
        # Non-root paths
        non_root_cases = ["Projects", "Projects/AI", "A/B/C"]
        for non_root_path in non_root_cases:
            folder_path = FolderPath.from_raw(non_root_path)
            assert not folder_path.is_root, f"'{non_root_path}' should not be root"
            
    def test_depth_property(self):
        """Test the depth property."""
        depth_cases = [
            ("", 0),
            ("Projects", 1),
            ("Projects/AI", 2),
            ("Projects/AI/Research", 3),
            ("A/B/C/D/E", 5),
        ]
        
        for raw_path, expected_depth in depth_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.depth == expected_depth, f"Depth test failed for '{raw_path}'"
            
    def test_string_representation(self):
        """Test string representations (__str__ and __repr__)."""
        test_cases = [
            ("Projects/AI/Research", "Projects/AI/Research"),
            ("Single", "Single"),
            ("", ""),
        ]
        
        for raw_path, expected_str in test_cases:
            folder_path = FolderPath.from_raw(raw_path)
            
            # Test __str__
            assert str(folder_path) == expected_str
            
            # Test __repr__
            repr_str = repr(folder_path)
            assert "FolderPath" in repr_str
            assert "_components" in repr_str


class TestFolderPathTupleBasedRepresentation:
    """Test tuple-based internal representation and operations."""
    
    def test_tuple_immutability(self):
        """Test that the internal tuple representation is immutable."""
        folder_path = FolderPath.from_raw("Projects/AI/Research")
        components = folder_path.components
        
        assert isinstance(components, tuple)
        
        # Try to modify the tuple (should fail)
        with pytest.raises(TypeError):
            components[0] = "Modified"
            
    def test_tuple_prefix_matching_algorithm(self):
        """Test that is_parent_of uses tuple prefix matching."""
        parent = FolderPath.from_raw("Projects/AI")
        child = FolderPath.from_raw("Projects/AI/Research")
        
        # Manual tuple prefix check
        parent_components = parent.components
        child_components = child.components
        
        expected_result = (
            len(parent_components) < len(child_components) and
            parent_components == child_components[:len(parent_components)]
        )
        
        actual_result = parent.is_parent_of(child)
        assert actual_result == expected_result, "is_parent_of should use tuple prefix matching"
        
    def test_exact_component_matching(self):
        """Test that matching is based on exact component equality."""
        # These should not match because components are different
        test_cases = [
            ("Proj", "Project"),  # Different length
            ("AI", "ai"),  # Different case
            ("Research ", "Research"),  # Trailing space
            (" Data", "Data"),  # Leading space
        ]
        
        for comp1, comp2 in test_cases:
            folder1 = FolderPath.from_raw(comp1)
            folder2 = FolderPath.from_raw(comp2)
            
            assert not folder1.is_parent_of(folder2)
            assert not folder2.is_parent_of(folder1)


class TestFolderPathEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_components_handling(self):
        """Test handling of empty components in paths."""
        # Multiple slashes should be normalized to single components
        test_cases = [
            ("A//B", ("A", "B")),
            ("A///B", ("A", "B")),
            ("//A//B//", ("A", "B")),
            ("A/////B", ("A", "B")),
        ]
        
        for raw_path, expected in test_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected
            
    def test_whitespace_handling(self):
        """Test handling of whitespace in paths."""
        test_cases = [
            ("  A  /  B  ", ("A", "B")),
            (" A/B ", ("A", "B")),
            ("A / B", ("A", "B")),
            ("   /A/B/   ", ("A", "B")),
        ]
        
        for raw_path, expected in test_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected
            
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        valid_cases = [
            ("Projects/AI-Research", ("Projects", "AI-Research")),
            ("Data_Science/ML", ("Data_Science", "ML")),
            ("Research/2023", ("Research", "2023")),
            ("生物学/研究", ("生物学", "研究")),  # Unicode characters
            ("Café/Résumé", ("Café", "Résumé")),  # Accented characters
        ]
        
        for raw_path, expected in valid_cases:
            folder_path = FolderPath.from_raw(raw_path)
            assert folder_path.components == expected
            
    def test_long_paths(self):
        """Test handling of long paths."""
        # Create a deep path
        components = [f"Level{i}" for i in range(1, 11)]  # Level1 through Level10
        long_path = "/".join(components)
        expected_components = tuple(components)
        
        folder_path = FolderPath.from_raw(long_path)
        assert folder_path.components == expected_components
        assert folder_path.depth == 10


class TestFolderPathIntegration:
    """Test integration with other parts of the system."""
    
    def test_exception_integration(self):
        """Test integration with LabArchivesMCPException."""
        # Test that exceptions have proper structure
        with pytest.raises(LabArchivesMCPException) as exc_info:
            FolderPath.from_raw("invalid/../path")
            
        exception = exc_info.value
        assert hasattr(exception, 'message')
        assert hasattr(exception, 'code')
        assert hasattr(exception, 'context')
        assert exception.code == 400
        
    def test_config_integration(self):
        """Test integration with configuration system."""
        # This test verifies that FolderPath works with typical config values
        typical_config_paths = [
            "Projects/AI",
            "Research/Chemistry",
            "Data/Analysis",
            "",  # Root path
        ]
        
        for config_path in typical_config_paths:
            # Test that we can create FolderPath from typical config values
            folder_path = FolderPath.from_raw(config_path)
            assert isinstance(folder_path, FolderPath)
            
    def test_performance_characteristics(self):
        """Test performance characteristics of FolderPath operations."""
        # Create many FolderPath instances
        paths = [f"Level{i}/Sublevel{j}" for i in range(1, 50) for j in range(1, 10)]
        folder_paths = [FolderPath.from_raw(path) for path in paths]
        
        # Test that creation and comparison is efficient
        assert len(folder_paths) == len(paths)
        
        # Test comparison operations
        parent = FolderPath.from_raw("Level1")
        child_count = sum(1 for fp in folder_paths if parent.is_parent_of(fp))
        assert child_count > 0  # Should find some children


class TestFolderPathParametrized:
    """Parameterized tests for comprehensive coverage."""
    
    @pytest.mark.parametrize("raw_path,expected_components", [
        ("A", ("A",)),
        ("A/B", ("A", "B")),
        ("A/B/C", ("A", "B", "C")),
        ("", ()),
        ("/", ()),
        ("A/", ("A",)),
        ("/A", ("A",)),
        ("A//B", ("A", "B")),
        ("  A  /  B  ", ("A", "B")),
    ])
    def test_from_raw_parametrized(self, raw_path, expected_components):
        """Parameterized test for from_raw method."""
        folder_path = FolderPath.from_raw(raw_path)
        assert folder_path.components == expected_components
        
    @pytest.mark.parametrize("parent_str,child_str,expected", [
        ("A", "A/B", True),
        ("A/B", "A/B/C", True),
        ("", "A", True),
        ("A", "A", False),
        ("A/B", "A", False),
        ("A", "B", False),
        ("Chem", "Chemistry", False),  # G-2 test case
        ("Lab", "Laboratory", False),  # Similar vulnerability
    ])
    def test_is_parent_of_parametrized(self, parent_str, child_str, expected):
        """Parameterized test for is_parent_of method."""
        parent = FolderPath.from_raw(parent_str)
        child = FolderPath.from_raw(child_str)
        result = parent.is_parent_of(child)
        assert result == expected, f"Failed: '{parent_str}' parent of '{child_str}' should be {expected}"


# Performance and stress tests
class TestFolderPathStress:
    """Stress tests for FolderPath under various conditions."""
    
    def test_many_components(self):
        """Test FolderPath with many components."""
        components = [f"Component{i}" for i in range(100)]
        path = "/".join(components)
        
        folder_path = FolderPath.from_raw(path)
        assert folder_path.depth == 100
        assert len(folder_path.components) == 100
        
    def test_very_long_component_names(self):
        """Test FolderPath with very long component names."""
        long_component = "A" * 255  # Very long component name
        path = f"Projects/{long_component}/Research"
        
        folder_path = FolderPath.from_raw(path)
        assert folder_path.components == ("Projects", long_component, "Research")
        
    def test_many_comparisons(self):
        """Test many comparison operations."""
        base_paths = [FolderPath.from_raw(f"Base{i}") for i in range(50)]
        test_paths = [FolderPath.from_raw(f"Base{i}/Child{j}") for i in range(50) for j in range(10)]
        
        # Perform many comparisons
        comparison_count = 0
        for base in base_paths:
            for test in test_paths:
                base.is_parent_of(test)
                comparison_count += 1
                
        assert comparison_count == 50 * 50 * 10  # 25,000 comparisons