#!/bin/bash
# Quick release script for v0.1.0 JOSS submission
# Run from repository root

set -e

echo "🚀 Preparing lab_archives_mcp v0.1.0 for JOSS submission"
echo ""

# Step 1: Verify we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: Not on main branch (currently on: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Check for uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo "📝 Uncommitted changes detected:"
    git status -s
    echo ""
    read -p "Commit these changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        git commit -m "chore: prepare v0.1.0 release for JOSS submission

- Add MIT LICENSE
- Add CONTRIBUTING.md and CODE_OF_CONDUCT.md
- Add GitHub Actions CI workflow
- Add JOSS paper (paper.md and paper.bib)
- Update README with badges and license info
- Update CHANGELOG for v0.1.0 release
- Add community templates (PR, issue templates)"
    fi
fi

# Step 3: Run unit tests
echo ""
echo "🧪 Running unit tests..."
conda run -p ./conda_envs/pol-dev pytest -m "not integration" -q || {
    echo "⚠️  Some tests failed. Review output above."
    read -p "Continue with release anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

# Step 4: Tag release
echo ""
echo "🏷️  Creating release tag v0.1.0..."
git tag -a v0.1.0 -m "Release v0.1.0 for JOSS submission

LabArchives MCP Server - AI Integration for Electronic Lab Notebooks

Core Features:
- Read-only MCP server for LabArchives ELN
- Semantic vector search across notebook content
- Integration with Claude Desktop and Windsurf
- Comprehensive test suite and CI
- MIT licensed

See CHANGELOG.md for full release notes."

# Step 5: Push to GitHub
echo ""
echo "📤 Pushing to GitHub..."
read -p "Push main branch and v0.1.0 tag to origin? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin main
    git push origin v0.1.0
    echo "✅ Pushed to GitHub"
else
    echo "⏭️  Skipped push. Run manually: git push origin main && git push origin v0.1.0"
fi

# Step 6: Instructions for GitHub Release
echo ""
echo "✅ Release tag v0.1.0 created!"
echo ""
echo "📋 Next steps:"
echo "1. Create GitHub Release:"
echo "   - Go to: https://github.com/SamuelBrudner/lab_archives_mcp/releases/new"
echo "   - Select tag: v0.1.0"
echo "   - Title: 'v0.1.0 - JOSS Submission Release'"
echo "   - Copy release notes from CHANGELOG.md"
echo "   - Publish release"
echo ""
echo "2. Update paper.md:"
echo "   - Add your ORCID ID (line 11)"
echo "   - Review author affiliation"
echo ""
echo "3. Submit to JOSS:"
echo "   - Go to: https://joss.theoj.org/papers/new"
echo "   - Repository URL: https://github.com/SamuelBrudner/lab_archives_mcp"
echo "   - Follow JOSS submission wizard"
echo ""
echo "📚 See JOSS_READY.md for complete checklist"
