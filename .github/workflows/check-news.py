"""Check if the PR has a news item.

Put a warning comment if it doesn't.
"""
import os
from github import Github, PullRequest
import re
from fnmatch import fnmatch


def get_added_files(pr: PullRequest.PullRequest):
    for file in pr.get_files():
        if file.status == "added":
            yield file.filename
            print(file)


def check_news_file(pr):
    return any(
        map(lambda file_name: fnmatch(file_name, "*/news/*.rst"), get_added_files(pr))
    )


def get_pr_number():
    pattern = re.compile(r"pull/(\d+)/")
    matches = pattern.findall(os.environ["GITHUB_REF"])
    return int(matches[0])


def check_issue_comment(pr: PullRequest.PullRequest):
    for comment in pr.get_issue_comments():
        print(comment.user, comment.id)


def main():
    # using an access token
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo = gh.get_repo(os.environ["GITHUB_REPOSITORY"])
    pr = repo.get_pull(get_pr_number())
    has_news_added = check_news_file(pr)
    check_issue_comment(pr)

    if not has_news_added:
        print("No news item found")

        pr.create_issue_comment(
            "Warning! No news item is found. "
            "If this is user facing change, please add a news item from `news/Template.rst`."
        )


if __name__ == "__main__":
    main()
