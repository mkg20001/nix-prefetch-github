import nix_prefetch_github
import pytest
from effect.testing import perform_sequence


def test_prefetch_github_actual_prefetch():
    seq = [
        (
            nix_prefetch_github.GetCommitInfo(
                owner='seppeljordan',
                repo='pypi2nix'
            ),
            lambda i: {'sha': 'TEST_REVISION'}
        ),
        (
            nix_prefetch_github.TryPrefetch(
                owner='seppeljordan',
                repo='pypi2nix',
                rev='TEST_REVISION',
                sha256=nix_prefetch_github.trash_sha256,
            ),
            lambda i: {
                'output':
                "output path TESTPATH has TEST hash 'TEST_ACTUALHASH' when TESTREST"
            }
        ),
        (
            nix_prefetch_github.TryPrefetch(
                owner='seppeljordan',
                repo='pypi2nix',
                rev='TEST_REVISION',
                sha256='TEST_ACTUALHASH',
            ),
            lambda i: None
        )
    ]
    eff = nix_prefetch_github.prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        hash_only=False
    )
    prefetch_result = perform_sequence(seq, eff)
    assert prefetch_result['rev'] == 'TEST_REVISION'
    assert prefetch_result['sha256'] == 'TEST_ACTUALHASH'


def test_prefetch_github_no_actual_prefetch():
    seq = [
        (
            nix_prefetch_github.GetCommitInfo(
                owner='seppeljordan',
                repo='pypi2nix'
            ),
            lambda i: {'sha': 'TEST_REVISION'}
        ),
        (
            nix_prefetch_github.TryPrefetch(
                owner='seppeljordan',
                repo='pypi2nix',
                rev='TEST_REVISION',
                sha256=nix_prefetch_github.trash_sha256,
            ),
            lambda i: {
                'output':
                "output path TESTPATH has TEST hash 'TEST_ACTUALHASH' when TESTREST"
            }
        ),
    ]
    eff = nix_prefetch_github.prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        hash_only=True
    )
    prefetch_result = perform_sequence(seq, eff)
    assert prefetch_result['rev'] == 'TEST_REVISION'
    assert prefetch_result['sha256'] == 'TEST_ACTUALHASH'
