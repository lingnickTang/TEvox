from langchain_core.prompts import PromptTemplate

prompt = """<ROLE> You are an autonomous agent with available tools to complete the task. </ROLE>
{% if tools %}
<TOOLS>
{{ tools }}
</TOOLS>
{% endif -%}
{% if experience %}
<EXPERIENCE>
{% for e in experience %}
- {{ e }}
{% endfor %}
</EXPERIENCE>
{% endif -%}
{% if context %}
<CONTEXT>
{{ context }}
</CONTEXT>
{% endif -%}
{% if task_tree %}
<TASK TREE>
{{ task_tree }}
</TASK TREE>
{% endif %}
{% if task_stack %}
<TASK STACK (BOTTOM)>
{{ task_stack }}
</TASK STACK (TOP)>
{% endif -%}
{% if tasks %}
<PLANNING>
{% for task in tasks %}
{% if task.subtasks %}
The remaining subtasks of the task `{{ task }}` is as follows:
{% for subtask in task.subtasks %}
- {{ subtask }}
{% endfor %}
{% endif %}
{% endfor %}
</PLANNING>
{% endif -%}
{% if progress %}
<PROGRESS>
{% for p in progress %}
- {{ p }}
{% endfor %}
</PROGRESS>
{% endif -%}"""


system_prompt = PromptTemplate.from_template(template=prompt, template_format="jinja2")

breakdown_or_execution_prompt = """Based on the execution progress and user feedback, to efficiently complete the current task `{task}`, evaluate whether to break it down or take actions immediately. If further decomposition to reduce complexity is necessary, return `breakdown`. If taking actions immediately to get feedback is necessary, return `execution`. Finally, output in JSON format:
```json
{{
    "reason": "Explain why the decision is prioritized for task completion.",
    "decision": "breakdown | execution"
}}
```"""

# breakdown_prompt = """To efficiently complete the current task `{task}`, analyze which subtasks are still necessary to be completed. Finally, output the subtasks in a JSON list, each item including its type, name, and spec, formatted as follows:
# ```json
# [
#     {{
#         "type": "The type of the task{schema}",
#         "name": "The name of the task",
#         "spec": "The specification of the task"
#     }}
# ]
# ```"""

breakdown_prompt = """Based on the execution progress and user feedback, to efficiently complete the current task `{task}`, analyze which subtasks are still necessary to be completed. Finally, output the subtasks in a JSON list, each item including its name and spec, formatted as follows:
```json
[
    {{
        "name": "The name of the task",
        "spec": "The specification of the task"
    }}
]
```"""

continue_or_terminate_prompt = """Based on the execution progress and user feedback, evaluate whether the final task `{task}` has been verified as completed. If the final task has not yet been verified as completed, return `continue`. If the final task has been verified as completed, return `terminate`. Finally, output in JSON format:
```json
{{
    "reason": "Explain why the decision is prioritized for task completion.",
    "decision": "continue | terminate"
}}
```"""

continue_or_backtrack_prompt = """Based on the execution progress and user feedback, evaluate whether the current task `{task}` is still necessary to be completed. If it is necessary to continue the current task, return `continue`. If it is necessary to terminate the current task, return `backtrack`. Finally, output in JSON format:
```json
{{
    "reason": "Explain why the decision is prioritized for task completion.",
    "decision": "continue | backtrack"
}}
```"""

# schedule_prompt = """To efficiently complete the current task `{task}`, schedule the highest-priority task based on the dependencies among the above tasks. Finally, output the scheduled task in JSON format, including its type, name, and spec, formatted as follows:
# ```json
# {{
#     "type": "The type of the task{schema}",
#     "name": "The name of the task",
#     "spec": "The specification of the task"
# }}
# ```"""

execution_prompt = """Based on the execution progress and user feedback, to efficiently complete the current task `{task}`, determine the highest-priority action could be taken next. Finally, output in JSON format:
```json
{{
    "tool_name": The tool to be executed, chosen from the `<| TOOLS |>` list,
    "tool_args": The parameters required for the tool.
}}
```"""

tool_output_prompt = """To efficiently complete the current task `{task}`, the tool `{tool_name}` with args `{tool_args}` has been executed and its output is as follows: `{output}`\n\n"""

context_summary_prompt = """Now that the feedback from the execution has been obtained, please extract the important original information from the execution feedback. Do not make anything up. Finally, output in Markdown format."""

task_progress_prompt = """Please report the status of the current task `{task}` based on actions taken and feedback received, including context and progress, excluding the next steps to be taken. Finally, output in Markdown format."""

remove_context_prompt = """To efficiently complete the current task `{task}`, please retain the context that is still necessary for subsequent tasks, remove the context that is no longer necessary for subsequent tasks, and output the IDs of the context needed to be removed in a JSON list. If no context is needed to be removed, return an empty list. Finally, output in JSON format:
```json
[
    The integer IDs of the context to be removed. If no context is to be removed, return an empty list.
]
```"""

solve_feedback_prompt = """After receiving the feedback `{feedback}`, what lessons can guide your next attempt when trying to complete the task in the future? Please summarize the methodology (including applicable scenarios and solution tutorials). Finally, output in Markdown format."""

eval_prompt = """You are an evaluator of the action taken by an autonomous agent.

### The task of the agent is as follows:
```
{task}
```

### The historical trajectories of the agent are as follows:
```
{context}
```

What lessons can guide your next attempt when trying to complete the task in the future? Please summarize the methodology (including applicable scenarios and solution tutorials). Finally, output in Markdown format."""


DEFAULT_EXPERIENCE = []

# DEFAULT_EXPERIENCE = [
#     # """Incremental Development Approach: In the lifecycle of development, an incremental approach is followed where the focus is on continuous feedback, quick iteration, and reducing complexity. The process begins with the design phase, where instead of completing the entire design and implementation upfront, the development progresses in small, manageable pieces. This means that for each function designed, testing and debugging should begin immediately, not after the entire design is completed. By adopting this method, feedback is gathered quickly, allowing for immediate adjustments and improvements.""",
#     """When gathering information, prioritize searching the internal knowledge base first. Only search the external web internet if the internal knowledge base does not provide the information.""",
#     """In an incremental development approach, the process is broken down into small, manageable steps. Each module is designed, developed, tested, and debugged individually before moving on to the next one. This allows for continuous feedback and quick adjustments, reducing complexity and improving the overall quality. The focus is on rapid iteration, ensuring that each part works correctly before proceeding to the next.""",
#     # """During the design phase, start by creating function mocks—use pseudocode with TODO comments instead of actual code. First, define the interfaces (e.g., in the header files) and write the pseudocode (e.g., in the source files) for each function. Once the mocks are in place, write test cases (including black-box, white-box, unit, and integration tests) to verify the correctness of the mock function. Afterward, run the tests, and if any issues arise, debug and fix the design errors.""",
#     """During the development phase, the code interface (including interface definition (such as header file) and code implementation (such as source file)) needs to be refined and compiled. After development, a report is required outlining which code units in which files need to be retested. Note: Each module should have its own separate subdirectory, such as in the subdirectory of the "lib" directory, such as /lib/.../xxx.h, /lib/.../xxx.c.""",
#     """During the testing phase, test cases (including black-box, white-box, unit, and integration tests) need to be refined, executed. After testing, a report is required based on the execution results of the test cases. Note: Each module should have its own separate subdirectory (The name of begins with `test_`), such as in the subdirectory of the "test" directory, i.e. /test/test_.../test_xxx.c""",
#     """During the debugging phase, if the tests have not been run yet, first run the tests. Investigate and analyze the root causes of the errors based on the test results by gathering more information. Finally, modify the code to fix the bug, and only when the test results are confirmed to be correct, can the task be considered complete.""",
#     """In PlatformIO, you don’t need to manually edit the CMakeLists.txt file because the framework automatically collects the code from the lib directory and the test code from the test directory. Also, avoid adding source files in the src directory. The code in src/main.c should have as little logic as possible because the PlatformIO testing framework will not collect the code from the src directory. If you write code in src, it won’t be tested.""",
#     """Getting Started with Unity Test Framework
# Test files are C/C++ files. Most often you will create a single test file for each C/C++ component that you want to test. The test file should include unity.h and the header for your C/C++ component to be tested.

# Next, a test file will include a setUp() and tearDown() function. The setUp function can contain anything you would like to run before each test. The tearDown function can contain anything you would like to run after each test. Both functions accept no arguments and return nothing. You may leave either or both of these blank if you have no need for them.

# The majority of the file will be a series of test functions. Test functions follow the convention of starting with the word test_ or spec_. You don’t HAVE to name them this way, but it makes it clear what functions are tests for other developers. Test functions take no arguments and return nothing. All test accounting is handled internally in Unity.

# Finally, at the bottom of your test file, you will write a main() function (setup() / loop() for Arduino, app_main() for Espressif IoT Development Framework). This function will call UNITY_BEGIN(), then RUN_TEST for each test, and finally UNITY_END(). This is what will actually trigger each of those test functions to run, so it is important that each function gets its own RUN_TEST call. Please remember to add each test to the main function.

# When you’re done, your test file will look something like this:

# #include "unity.h"
# #include "file_to_test.h"

# void setUp(void) {
#   // set stuff up here
# }

# void tearDown(void) {
#   // clean stuff up here
# }

# void test_function_should_doBlahAndBlah(void) {
#   // test stuff
# }

# void test_function_should_doAlsoDoBlah(void) {
#   // more test stuff
# }

# int runUnityTests(void) {
#   UNITY_BEGIN();
#   RUN_TEST(test_function_should_doBlahAndBlah);
#   RUN_TEST(test_function_should_doAlsoDoBlah);
#   return UNITY_END();
# }

# /**
#   * For ESP-IDF framework
#   */
# #include "freertos/FreeRTOS.h"
# #include "freertos/task.h"

# void app_main() {
#   // Wait ~5 seconds before the Unity test runner establishes connection with the board's Serial interface
#   // Important Note: Before running the tests, make sure to include a delay of at least 5 seconds to allow the Unity test runner to establish a proper connection with your board's serial interface.
#   vTaskDelay(pdMS_TO_TICKS(5000));  // Delay for 5 seconds

#   runUnityTests();
# }""",
#     #     """## Getting Started with Unity Test Framework
#     # To get started with testing your C/C++ code, you typically create a test file for each component you wish to test. The test file should include `unity.h` and the header file for the component you're testing.
#     # Each test file will generally have a `setUp()` and `tearDown()` function. The `setUp()` function runs before each test, and `tearDown()` runs after each test. Both functions take no arguments and return nothing, and you can leave them empty if you don’t need them.
#     # The main part of your test file will consist of test functions. Test functions should start with `test_` or `spec_` to make it clear that they are tests. These functions also take no arguments and return nothing. Unity handles all the test accounting internally.
#     # At the bottom of your test file, you’ll include a `main()` function (or `setup()` / `loop()` for Arduino, or `app_main()` for ESP-IDF). This function calls `UNITY_BEGIN()`, then `RUN_TEST()` for each of your test functions, and finally `UNITY_END()`. This triggers the execution of your tests. Be sure to call `RUN_TEST()` for each test function.
#     # Here’s an example structure of the test file:
#     # ```c
#     # #include "unity.h"
#     # #include "file_to_test.h"
#     # void setUp(void) {
#     #   // Setup code here
#     # }
#     # void tearDown(void) {
#     #   // Teardown code here
#     # }
#     # void test_function_should_doBlahAndBlah(void) {
#     #   // Test code here
#     # }
#     # void test_function_should_doAlsoDoBlah(void) {
#     #   // More test code here
#     # }
#     # int runUnityTests(void) {
#     #   UNITY_BEGIN();
#     #   RUN_TEST(test_function_should_doBlahAndBlah);
#     #   RUN_TEST(test_function_should_doAlsoDoBlah);
#     #   return UNITY_END();
#     # }
#     # // WARNING!!! PLEASE REMOVE UNNECESSARY MAIN IMPLEMENTATIONS //
#     # /**
#     #   * For native dev-platform or for some embedded frameworks
#     #   */
#     # int main(void) {
#     #   return runUnityTests();
#     # }
#     # /**
#     #   * For Arduino framework
#     #   */
#     # void setup() {
#     #   // Wait ~2 seconds before the Unity test runner
#     #   // establishes connection with the board's Serial interface
#     #   delay(2000);
#     #   runUnityTests();
#     # }
#     # void loop() {}
#     # /**
#     #   * For ESP-IDF framework
#     #   */
#     # #include "freertos/FreeRTOS.h"
#     # #include "freertos/task.h"
#     # void app_main() {
#     #   // Wait ~5 seconds before the Unity test runner establishes connection with the board's Serial interface
#     #   vTaskDelay(pdMS_TO_TICKS(5000));  // Delay for 5 seconds
#     #   runUnityTests();
#     # }
#     # Important Note: Before running the tests, make sure to include a delay of at least 5 seconds to allow the Unity test runner to establish a proper connection with your board's serial interface.""",
# ]
