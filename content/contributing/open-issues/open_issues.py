# SPDX-FileCopyrightText: 2024 Alec "tekktrik" Delaney
#
# SPDX-License-Identifier: MIT

"""
Script for getting open issues for Beeware projects.

Author(s): Alec "tekktrik" Delaney
"""

import json
import os
import sys

import jinja2
import requests

# These are the only repositories that get queried
REPO_NAMES = [
    "beeware",
    "beeware.github.io"
    "briefcase",
    "toga",
]

# Some other helpful globals to make life easier
GRAPHQL_URL = "https://api.github.com/graphql"
GRAPHQL_TEMPATE = "content/contributing/open-issues/issues_query.txt"
LEKTOR_TEMPLATE = "content/contributing/open-issues/contents.lr"


# Read the template for the GraphQL query
with open(GRAPHQL_TEMPATE, encoding="utf-8") as queryfile:
    graphql_text = queryfile.read()

# Read the template for the Lektor content file
with open(LEKTOR_TEMPLATE, encoding="utf-8") as lektorfile:
    lektor_text = lektorfile.read()

# Create Jinja templates from the file texts
jinja_env = jinja2.Environment()
graphql_template = jinja_env.from_string(graphql_text)
lektor_template = jinja_env.from_string(lektor_text)

# This is what will hold all the issues for all repositories
projects = {}

for repo_name in REPO_NAMES:
    # Keep track of issues for each repository, as well as the cursor for pagination (start is null)
    after_cursor = "null"
    all_issues = []

    # Due to pagination, multuple queries may be needed for each repository (max 100 issues each call)
    # When there are no more issues, we'll break out of this loop
    while True:
        # Render the GraphQL template with the specific repository and cursor position
        graphql_rendered = graphql_template.render(
            repo_name=repo_name, after_cursor=after_cursor
        )
        query_param = {"query": graphql_rendered}

        # Perform the GraphQL query
        resp = requests.post(
            GRAPHQL_URL,
            json=query_param,
            headers={
                "Authorization": f'Bearer {os.environ["GITHUB_TOKEN"]}',
            },
            timeout=5,
        )

        # Raise an issue in the CI if something went wrong
        if resp.status_code != 200:
            sys.exit(1)

        # Create an issue dict for with the title, URL, and list of label names for each issue, and add it to the repo's issue list
        repo_details = json.loads(resp.content)["data"]["organization"]["repository"]
        for issue_node in repo_details["issues"]["nodes"]:
            issue = {
                "title": issue_node["title"].replace("`", "\\`"),
                "url": issue_node["url"],
                "labels": [
                    label_node["name"] for label_node in issue_node["labels"]["nodes"]
                ],
            }
            all_issues.append(issue)

        # If there are additional issues for this reposistory, update the cursor and perform another query
        if repo_details["issues"]["pageInfo"]["hasNextPage"]:
            after_cursor = f'"{repo_details["issues"]["pageInfo"]["endCursor"]}"'
            continue

        # Otherwise, we're all done with the current repository
        break

    # Add the current repository's issues to the global project dictionary
    projects[repo_name] = all_issues

# Render the lektor content tempate with the newly projects' issues information
new_lektor_text = lektor_template.render(projects=projects)

# Save the now populated template text back to the lektor content file
with open(LEKTOR_TEMPLATE, mode="w", encoding="utf-8") as lektorfile:
    lektorfile.write(new_lektor_text)
