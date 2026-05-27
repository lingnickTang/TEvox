prefix_prompt = """The files have already been opened in the VSCode editor:
```
{files}
```\n\n"""

open_files_prompt = """The files and subdirectories of the directory `{directory_path}` are as follows:
```
{files}
```

Based on the progress, to efficiently complete the current task `{task}`, analyze which files and subdirectories are still necessary to be opened. Finally, output in JSON format:
```json
{{
    "files": [
        "The paths of the files to be viewed. If no files are necessary to be opened, return an empty list."
    ],
    "directories": [
        "The paths of the subdirectories to be viewed. If no subdirectories are necessary to be opened, return an empty list."
    ]
}}
```"""

# close_files_prompt = """Based on the progress, to efficiently complete the current task `{task}`, analyze which files are no longer necessary to be opened. Finally, output in JSON format:" \
# ```json
# {{
#     "files": [
#         "The paths of the files to be closed. If no files are necessary to be closed, return an empty list."
#     ]
# }}
# ```"""
