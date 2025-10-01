# GitHub Actions Workflow Notes

## IDE Warnings About Secret Access

Your IDE may show warnings like "Context access might be invalid" for GitHub secrets in `tests.yml`.

**This is expected and safe** - these are false positives. Here's why:

### GitHub Secrets Behavior

1. **Secrets can be undefined** - GitHub Actions allows referencing secrets that don't exist
2. **Empty secrets evaluate to empty string** - If a secret isn't configured, it's just `""`
3. **We handle this gracefully** - Steps use `continue-on-error: true` to prevent failures

### How It Works

```yaml
# This is CORRECT GitHub Actions syntax
env:
  LABARCHIVES_AKID: ${{ secrets.LABARCHIVES_AKID }}  # May be empty

# If secret doesn't exist:
# - It evaluates to empty string
# - Tests skip integration tests (they check for env vars)
# - CI doesn't fail (continue-on-error: true)
```

### Configuring Secrets (Optional)

To run integration tests in CI, add these secrets at:
`Settings → Secrets and variables → Actions → New repository secret`

Required for integration tests:
- `LABARCHIVES_AKID`
- `LABARCHIVES_PASSWORD`
- `LABARCHIVES_UID`
- `LABARCHIVES_REGION`

Optional for coverage upload:
- `CODECOV_TOKEN`

Optional for vector search tests:
- `PINECONE_API_KEY`

### References

- [GitHub Actions: Encrypted secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Using secrets in a workflow](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
