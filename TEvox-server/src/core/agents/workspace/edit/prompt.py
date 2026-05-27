edit_file_prompt = """The file you are currently editing is `{file_path}` and the content with line numbers is as follows:
```
{file_content}
```\n\n"""

get_edit_type_prompt = """Based on the progress, to efficiently complete the current task `{task}`, determine the edit type and edit range to be performed. Finally, output in JSON format:
```json
{{
    "edit_type": "insert | replace",
    "start_line": "The start line of the edit range.",
    "end_line": "The end line of the edit range."
}}
```"""

insert_prompt = """Based on the progress, to efficiently complete the current task `{task}`, output the new content to be inserted at the line {line}. Finally, output in Markdown format (only in one ```...``` block):
```
(The new content to be inserted without line numbers. When generating code, you MUST include detailed comments and comprehensive logging to facilitate verification of the program's correctness and to aid in debugging through log analysis.)
```"""

replace_prompt = """Based on the progress, to efficiently complete the current task `{task}`, output the new content to replace the content from the start line {start_line} to end line {end_line}. Finally, output in Markdown format (only in one ```...``` block):
```
(The new content to replace without line numbers. When generating code, you MUST include detailed comments and comprehensive logging to facilitate verification of the program's correctness and to aid in debugging through log analysis.)
```"""

merge_file_prompt = """The file you are currently editing is `{file_path}`.

The original content with line numbers is as follows:
```
{original_content}
```

After editing, the current content with line numbers is as follows:
```
{current_content}
```

Based on the progress, to efficiently complete the current task `{task}`, you should review the changes and output the final merged complete content in Markdown format (only in one ```...``` block):
```
(The final merged complete content without line numbers. Keep the actual content of the current file.)
```"""

# (The final merged complete content without line numbers. Keep the actual content instead of describing it in terms of what remains unchanged or omitting existing original content from the current file.)

continue_or_terminate_prompt = """The file you are currently editing is `{file_path}`.

The original content with line numbers is as follows:
```
{original_content}
```

After editing, the current content with line numbers is as follows:
```
{current_content}
```

Based on the progress, to efficiently complete the current task `{task}`, evaluate whether the content of current file `{file_path}` is fully complete. If you find that any file content is missing or incomplete, conclude that further editing is necessary and return `YES`. If you determine that the file content is complete and no additional edits are required, then conclude that editing should be terminated and return `NO`. Finally, output in JSON format:
```json
{{
    "reason": "Explain why the decision is prioritized for task completion.",
    "decision": "YES | NO"
}}
```"""
