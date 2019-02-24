import os
from tempfile import TemporaryDirectory

import nix_prefetch_github
import pytest
from effect import Effect, sync_perform
from effect.testing import perform_sequence
from nix_prefetch_github.io import cmd


requires_nix_build = pytest.mark.nix_build


def test_prefetch_github_actual_prefetch():
    seq = [
        (
            nix_prefetch_github.GetCommitHashForName(
                owner='seppeljordan',
                repo='pypi2nix',
                rev=None,
            ),
            lambda i: 'TEST_COMMIT',
        ),
        (
            nix_prefetch_github.CalculateSha256Sum(
                owner='seppeljordan',
                repo='pypi2nix',
                revision='TEST_COMMIT',
            ),
            lambda i: 'TEST_ACTUALHASH',
        ),
        (
            nix_prefetch_github.TryPrefetch(
                owner='seppeljordan',
                repo='pypi2nix',
                rev='TEST_COMMIT',
                sha256='TEST_ACTUALHASH',
            ),
            lambda i: None
        )
    ]
    eff = nix_prefetch_github.prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        prefetch=True
    )
    prefetch_result = perform_sequence(seq, eff)
    assert prefetch_result['rev'] == 'TEST_COMMIT'
    assert prefetch_result['sha256'] == 'TEST_ACTUALHASH'


def test_prefetch_github_no_actual_prefetch():
    seq = [
        (
            nix_prefetch_github.GetCommitHashForName(
                owner='seppeljordan',
                repo='pypi2nix',
                rev=None,
            ),
            lambda i: 'TEST_COMMIT',
        ),
        (
            nix_prefetch_github.CalculateSha256Sum(
                owner='seppeljordan',
                repo='pypi2nix',
                revision='TEST_COMMIT',
            ),
            lambda i: 'TEST_ACTUALHASH',
        ),
    ]
    eff = nix_prefetch_github.prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        prefetch=False,
    )
    prefetch_result = perform_sequence(seq, eff)
    assert prefetch_result['rev'] == 'TEST_COMMIT'
    assert prefetch_result['sha256'] == 'TEST_ACTUALHASH'


def test_prefetch_github_rev_given():
    commit_hash = '50553a665d2700c353ac41ab28c23b1027b7c1f0'
    seq = [
        (
            nix_prefetch_github.CalculateSha256Sum(
                owner='seppeljordan',
                repo='pypi2nix',
                revision=commit_hash,
            ),
            lambda i: 'TEST_ACTUALHASH',
        )
    ]
    eff = nix_prefetch_github.prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        prefetch=False,
        rev=commit_hash,
    )
    prefetch_result = perform_sequence(seq, eff)
    assert prefetch_result['rev'] == commit_hash
    assert prefetch_result['sha256'] == 'TEST_ACTUALHASH'


@requires_nix_build
def test_life_mode():
    results = nix_prefetch_github.nix_prefetch_github(
        owner='seppeljordan',
        repo='pypi2nix',
        prefetch=True,
        rev=None
    )
    assert 'sha256' in results.keys()


@requires_nix_build
def test_get_commit_hash_for_name_with_actual_github_repo():
    result = sync_perform(
        nix_prefetch_github.dispatcher(),
        Effect(nix_prefetch_github.GetCommitHashForName(
            owner='seppeljordan',
            repo='parsemon2',
            rev='master',
        ))
    )
    assert len(result) == 40


def test_is_sha1_hash_detects_actual_hash():
    text = '5a484700f1006389847683a72cd88bf7057fe772'
    assert nix_prefetch_github.is_sha1_hash(text)


def test_is_sha1_hash_returns_false_for_string_to_short():
    text = '5a484700f1006389847683a72cd88bf7057fe77'
    assert len(text) < 40
    assert not nix_prefetch_github.is_sha1_hash(text)


@requires_nix_build
def test_is_to_nix_expression_outputs_valid_nix_expr():
    for prefetch in [False, True]:
        output_dictionary = nix_prefetch_github.nix_prefetch_github(
            owner='seppeljordan',
            repo='pypi2nix',
            prefetch=prefetch,
            rev='master'
        )
        nix_expr_output = nix_prefetch_github.to_nix_expression(output_dictionary)

        with TemporaryDirectory() as temp_dir_name:
            nix_filename = temp_dir_name + '/output.nix'
            with open(nix_filename, 'w') as f:
                f.write(nix_expr_output)
            returncode, output = cmd(['nix-build', nix_filename, '--no-out-link'])
            assert returncode == 0


@pytest.mark.parametrize(
    'nix_build_output',
    (
        [
            "hash mismatch in fixed-output derivation '/nix/store/7pzdkrl1ddw9blkr4jymwavbxmxxdwm1-source':",
            "  wanted: sha256:1y4ly7lgqm03wap4mh01yzcmvryp29w739fy07zzvz15h2z9x3dv",
            "  got:    sha256:0x1x9dq4hnkdrdfbvcm6kaivrkgmmr4vp2qqwz15y5pcawvyd0z6",
            "error: build of '/nix/store/rfjcq0fcmiz7masslf7q27xs012v6mnp-source.drv' failed",
        ],
        [
            "fixed-output derivation produced path '/nix/store/cn22m5wz95whqi4wgzfw5cfz9knslak4-source' with sha256 hash '0x1x9dq4hnkdrdfbvcm6kaivrkgmmr4vp2qqwz15y5pcawvyd0z6' instead of the expected hash '0401067152dx9z878d4l6dryy7f611g2bm8rq4dyn366w6c9yrcb'",
            "cannot build derivation '/nix/store/8savxwnx8yw7r1ccrc00l680lmq5c15f-output.drv': 1 dependencies couldn't be built",
        ],
        [
            "output path '/nix/store/z9zpz2yqx1ixn4xl1lsrk0f83rvp7srb-source' has r:sha256 hash '0x1x9dq4hnkdrdfbvcm6kaivrkgmmr4vp2qqwz15y5pcawvyd0z6' when '1mkcnzy1cfpwghgvb9pszhy9jy6534y8krw8inwl9fqfd0w019wz' was expected",
        ],
    )
)
def test_that_detect_actual_hash_from_nix_output_works_for_multiple_version_of_nix(
        nix_build_output,
):
    actual_sha256_hash = '0x1x9dq4hnkdrdfbvcm6kaivrkgmmr4vp2qqwz15y5pcawvyd0z6'
    assert (
        actual_sha256_hash ==
        nix_prefetch_github.detect_actual_hash_from_nix_output(nix_build_output)
    )
