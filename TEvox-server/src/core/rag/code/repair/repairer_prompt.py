# evox-server/src/core/rag/code/repair/repairer_prompt.py

REPAIRER_PROMPTS = {
"simple_test_generation": """
As a professional C++ test engineer, please generate comprehensive unit tests for the following code using the ESP-IDF framework.

Test Template Example:
Example 1:
#include <stdio.h>
#include <assert.h>
#include "foo.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs_flash.h>
using namespace std;

static void foo_test_task(void* param) {{
    printf("Starting foo_test_task...\\n");
    // Test case 1: Normal addition
    int result1 = foo_add(2, 3);
    assert(result1 == 5);
    printf("✓ Test case 1 passed: 2 + 3 = %d\\n", result1);
    
    // Test case 2: 
    ...
    vTaskDelete(NULL);
}}

extern "C" void app_main(void) {{
    // Initialize NVS Flash
    ESP_ERROR_CHECK(nvs_flash_erase());
    ESP_ERROR_CHECK(nvs_flash_init());
    printf("NVS Flash initialization completed\\n");

    xTaskCreate(foo_test_task, "foo_test_task", 4096, NULL, 5, NULL);
}}

Example 2:
#include <stdio.h>
#include <string>
#include <inttypes.h>
#include "settings.h"
#include "EspNvsStorage.h"
#include "EspLogger.h"
#include <esp_log.h>
#include <nvs_flash.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

using namespace std;

static void nvs_storage_test_task(void* param) {{
    printf("Starting nvs_storage_test_task...\\n");
    // Test case 1: Normal string operations
    {{ 
        // the actual implementation from the implementation file EspNvsStorage.h
        EspNvsStorage storage1("test_ns1", true); // The namespace should less than 15 character;
        storage1.SetString("key1", "hello"); // The key should less than 15 character;
        string result1 = storage1.GetString("key1", "default");
        if (result1 == "hello") {{
            printf("✓ Test case 1 passed: String set/get works\\n");
        }} else {{  
            printf("✗ Test case 1 failed: Expected 'hello', got '%s'\\n", result1.c_str());
        }}
    }}

    // Test case 2:
    ...
    vTaskDelete(NULL);
}}

extern "C" void app_main(void) {{
    // Initialize NVS Flash
    ESP_ERROR_CHECK(nvs_flash_erase());
    ESP_ERROR_CHECK(nvs_flash_init());
    printf("NVS Flash initialization completed\\n");
    xTaskCreate(nvs_storage_test_task, "nvs_storage_test_task", 4096, NULL, 5, NULL);
}}
Source Code:
{code}

Please directly generate code that can be compiled and executed inside the ```cpp ``` mark:
""",
    "test_generation": """
As a professional C++ test engineer, please generate comprehensive unit tests for the following code using the ESP-IDF framework.

Test Template Example:
Example 1:
#include <stdio.h>
#include <assert.h>
#include "foo.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs_flash.h>
using namespace std;

static void foo_test_task(void* param) {{
    printf("Starting foo_test_task...\\n");
    // Test case 1: Normal addition
    int result1 = foo_add(2, 3);
    assert(result1 == 5);
    printf("✓ Test case 1 passed: 2 + 3 = %d\\n", result1);
    
    // Test case 2: 
    ...
    vTaskDelete(NULL);
}}

extern "C" void app_main(void) {{
    // Initialize NVS Flash
    ESP_ERROR_CHECK(nvs_flash_erase());
    ESP_ERROR_CHECK(nvs_flash_init());
    printf("NVS Flash initialization completed\\n");

    xTaskCreate(foo_test_task, "foo_test_task", 4096, NULL, 5, NULL);
}}

Example 2:
#include <stdio.h>
#include <string>
#include <inttypes.h>
#include "settings.h"
#include "EspNvsStorage.h"
#include "EspLogger.h"
#include <esp_log.h>
#include <nvs_flash.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

using namespace std;

static void nvs_storage_test_task(void* param) {{
    printf("Starting nvs_storage_test_task...\\n");
    // Test case 1: Normal string operations
    {{ 
        // the actual implementation from the implementation file EspNvsStorage.h
        EspNvsStorage storage1("test_ns1", true); // The namespace should less than 15 character;
        storage1.SetString("key1", "hello"); // The key should less than 15 character;
        string result1 = storage1.GetString("key1", "default");
        if (result1 == "hello") {{
            printf("✓ Test case 1 passed: String set/get works\\n");
        }} else {{  
            printf("✗ Test case 1 failed: Expected 'hello', got '%s'\\n", result1.c_str());
        }}
    }}

    // Test case 2:
    ...
    vTaskDelete(NULL);
}}

extern "C" void app_main(void) {{
    // Initialize NVS Flash
    ESP_ERROR_CHECK(nvs_flash_erase());
    ESP_ERROR_CHECK(nvs_flash_init());
    printf("NVS Flash initialization completed\\n");
    xTaskCreate(nvs_storage_test_task, "nvs_storage_test_task", 4096, NULL, 5, NULL);
}}

Code Description: {description}

Source File Name: {filename}
Interface Files Available: {interfaces_file_list}
Implementation Files Available: {implementations_file_list}
Source Code:
{code}

Requirements:
1. Use the test template as few-shot examples for the function testing
2. All interface and implementation files can be used directly from the interfaces/implementations directories. There is no need to use mock methods. (The interface and implementation folders are already included in the include path, so you only need to use #include "<filename.h>" without adding any folder path.)
3. Please directly generate code that can be compiled and executed inside the ```cpp ``` mark.
4. Follow the SOLID principles to generate test code.
5. use the actual implementation from the implementation files instead of the mock methods.
""",

    "test_analysis": """
Analyze the test execution results and determine whether the code has errors.

Test Results:
{test_results}

List of nodes id and their codes:
{nodes_info}

Rules for analysis:
1. The main.cc file is the test code. Use the node id (from the list of nodes) as the test node id.
2. Lines containing "Failed", "Error", etc. do not necessarily indicate errors—they must be further analyzed according to the logic of the test.
3. You need to analyze whether the errors are in the test code itself or in the source code itself or both, then select relevant node ids and provide detailed error analysis.

Please first output the analysis process step by step according to the test results and then output your results in the following JSON format inside the ```json ``` mark:
{{
    "has_errors": Whether there are errors (true/false),
    "error_node_ids": [The node ids that have errors],
    "error_analysis": {{node_id: detailed error analysis, ...}}
}}

Please analyze carefully and output only the JSON.
""",

    "code_repair": """
As a professional C++ repair expert, please fix the following code based on the analysis:

Interface Files Available: {interfaces_file_list}
Implementation Files Available: {implementations_file_list}

All interface and implementation files can be used directly from the interfaces/implementations directories. There is no need to use mock methods. (The interface and implementation folders are already included in the include path, so you only need to use #include "<filename.h>" without adding any folder path.)

Code to be repaired:
{code}

Analysis Result:
{analysis_result}

Rules for repair:
1. If the information is insufficient to fix the code, you can try to add additional output logic to obtain more error information.
2. Ensure that the generated test file covers all the constraints and requirements of the original functionality.

Please directly generate code that can be compiled and executed inside the ```cpp ``` mark.
"""
}
