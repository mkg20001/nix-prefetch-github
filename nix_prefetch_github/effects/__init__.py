import json
import os
import re
import sys
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import urlopen

import effect.io
from effect import (
    ComposedDispatcher,
    Effect,
    TypeDispatcher,
    sync_perform,
    sync_performer,
)
from effect.do import do

from ..command import run_command
from ..core import (
    AbortWithErrorMessage,
    CheckGitRepoIsDirty,
    DetectGithubRepository,
    DetectRevision,
    GetCurrentDirectory,
    GetRevisionForLatestRelease,
    GithubRepository,
    ShowWarning,
    TryPrefetch,
)
from ..remote_list_factory import RemoteListFactoryImpl
from ..templates import output_template

trash_sha256 = "1y4ly7lgqm03wap4mh01yzcmvryp29w739fy07zzvz15h2z9x3dv"
base_dispatcher = effect.ComposedDispatcher(
    [effect.base_dispatcher, effect.io.stdio_dispatcher]
)


def make_effect_dispatcher(mapping):
    def make_performer(effect):
        def _performer(dispatcher, intent):
            return sync_perform(dispatcher, effect(intent))

        return _performer

    return effect.TypeDispatcher(
        {
            the_type: sync_performer(make_performer(perform_effect))
            for the_type, perform_effect in mapping.items()
        }
    )


def dispatcher():
    prefetch_dispatcher = TypeDispatcher(
        {
            AbortWithErrorMessage: abort_with_error_message_performer,
            GetCurrentDirectory: get_current_directory_performer,
            ShowWarning: show_warning_performer,
            GetRevisionForLatestRelease: get_revision_for_latest_release_performer,
            TryPrefetch: try_prefetch_performer,
            CheckGitRepoIsDirty: check_git_repo_is_dirty_performer,
        }
    )
    composed_performers = make_effect_dispatcher(
        {
            DetectGithubRepository: detect_github_repository,
            DetectRevision: detect_revision,
        }
    )
    return ComposedDispatcher(
        [base_dispatcher, prefetch_dispatcher, composed_performers]
    )


@do
def detect_github_repository(intent):
    returncode, stdout = run_command(
        command=["git", "remote", "get-url", intent.remote], cwd=intent.directory
    )
    match = re.match("(git@github.com:|https://github.com/)(.+)/(.+).git", stdout)
    if not match:
        yield Effect(
            AbortWithErrorMessage(
                message=f"Remote '{intent.remote}' is not a link to a github repository"
            )
        )
    else:
        owner = match.group(2)
        name = match.group(3)
        return GithubRepository(
            name=name,
            owner=owner,
        )


@do
def detect_revision(intent):
    _, stdout = run_command(command=["git", "rev-parse", "HEAD"], cwd=intent.directory)
    return stdout[:-1]


@sync_performer
def get_current_directory_performer(_, _intent):
    return os.getcwd()


@sync_performer
def try_prefetch_performer(_, try_prefetch):
    nix_code_calculate_hash = output_template(
        owner=try_prefetch.repository.owner,
        repo=try_prefetch.repository.name,
        rev=try_prefetch.rev,
        sha256=try_prefetch.sha256,
        fetch_submodules=try_prefetch.fetch_submodules,
    )
    with TemporaryDirectory() as temp_dir_name:
        nix_filename = temp_dir_name + "/prefetch-github.nix"
        with open(nix_filename, "w") as f:
            f.write(nix_code_calculate_hash)
        result = run_command(
            command=["nix-build", nix_filename, "--no-out-link"],
            merge_stderr=True,
        )
        return result


def perform_effects(effects):
    return sync_perform(dispatcher(), effects)


@sync_performer
def abort_with_error_message_performer(_, intent):
    print(intent.message, file=sys.stderr)
    exit(1)


@sync_performer
def show_warning_performer(_, intent):
    print(f"WARNING: {intent.message}", file=sys.stderr)


@sync_performer
def check_git_repo_is_dirty_performer(_, intent):
    returncode, _ = run_command(
        command=["git", "diff", "HEAD", "--quiet"],
        cwd=intent.directory,
    )
    if returncode == 128:
        raise Exception(
            f"Repository at {intent.directory} does not contain any commits"
        )
    return returncode != 0


@sync_performer
def get_revision_for_latest_release_performer(_, intent):
    url = f"https://api.github.com/repos/{intent.repository.owner}/{intent.repository.name}/releases/latest"
    try:
        with urlopen(url) as response:
            encoding = response.info().get_content_charset("utf-8")
            content_data = response.read()
    except HTTPError:
        return None
    content_json = json.loads(content_data.decode(encoding))
    tag = content_json["tag_name"]
    remote_list = RemoteListFactoryImpl().get_remote_list(intent.repository)
    assert remote_list
    return remote_list.tag(tag)
