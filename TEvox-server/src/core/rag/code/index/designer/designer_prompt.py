# evox-server/src/core/rag/code/index/designer/designer_prompt.py

DESIGNER_PROMPTS = {
   "analyze_dependencies": """As a professional software engineer, please analyze the current module implementation and identify which reference nodes have relevant functionality to parts of the current module.

Please perform the following analysis:
1. Examine the current module implementation to identify all external dependencies, function calls, variable references, and node instantiations.
2. Match these dependencies against the provided reference nodes and descriptions.
3. Identify which reference nodes have relevant functionality to parts of the current module.

Please output your results in the following YAML format inside the ```yaml ``` mark:
nodes: Information for all reference nodes
   - id: Name of the node

Below is the concrete implementation of the current module:
{what}

Below are the provided reference nodes and their descriptions:
{reference_nodes_and_descriptions}
""",

   "dependency_decouple": """As a professional software engineer, please perform the following tasks:

1. Analyze and categorize all function APIs and variables that the current module depends on or utilizes according to the provided node definitions and descriptions (ignore the functions and variables that depend on std standard library).
2. If any of the identified functional categories already have relevant interface/implementation in the provided node definitions and descriptions, you should try to reuse them.
3. Otherwise, in accordance with the Dependency Inversion Principle, abstract each functional group as a dedicated interface class. Ensure that the id, description, and code of each interface class are concise and decoupled from any concrete implementation.
4. For each interface class, provide a concrete implementation as it would be used within the current module (place the implementation in the 'code' field), and establish edge relationships between the interface and its implementation.

First, output your intermediate analysis process. Then, present your final results in the following YAML format inside the ```yaml ``` mark:
nodes: Information for all interface and implementation nodes
   - id: name(e.g. ILogger for logging interface, EspLogger for logging implementation)
   - type: "interface" or "implementation"
   - description: Describe WHAT the code does - the functional purpose, responsibilities, and behavior, considering the context.
   - code: |
     Runnable code of the node (include all necessary #include statements; for interface node, provide the interface declaration, for implementation node, provide the detailed runnable implementation code)

Below is the concrete implementation of the current module:
{what}

Below are the provided nodes and their descriptions:
{reference_nodes_and_descriptions_and_implementation}
""",

   "refactor_origin_code": """
As an experienced software engineer, please:

1. Refactor the current module according to the provided interface modules and implementation modules.
2. **Use dependency injection** to include the required modules instead of direct API calls.
3. Apply SOLID principles, particularly the Dependency Inversion Principle.
4. **Generate both header and source files** for the refactored module.

**REFACTORING REQUIREMENTS**:
- Use dependency injection for all external dependencies
- Apply SOLID principles throughout the refactoring
- Ensure proper separation of interface and implementation

Refactoring Example:
Before refactoring:
// Settings.h
#ifndef SETTINGS_H
#define SETTINGS_H

#include <string>
#include <nvs_flash.h>

class Settings {{
public:
    Settings(const std::string& ns, bool read_write = false);
    ~Settings();

    std::string GetString(const std::string& key, const std::string& default_value = "");
    void SetString(const std::string& key, const std::string& value);
    int32_t GetInt(const std::string& key, int32_t default_value = 0);
    void SetInt(const std::string& key, int32_t value);
    void EraseKey(const std::string& key);
    void EraseAll();

private:
    std::string ns_;
    nvs_handle_t nvs_handle_ = 0;
    bool read_write_ = false;
    bool dirty_ = false;
}};
#endif

// Settings.cc
#include "Settings.h"

#include <esp_log.h>
#include <nvs_flash.h>

#define TAG "Settings"

Settings::Settings(const std::string& ns, bool read_write) : ns_(ns), read_write_(read_write) {{
    nvs_open(ns.c_str(), read_write_ ? NVS_READWRITE : NVS_READONLY, &nvs_handle_);
}}
...
void Settings::SetString(const std::string& key, const std::string& value) {{
    if (read_write_) {{
        ESP_ERROR_CHECK(nvs_set_str(nvs_handle_, key.c_str(), value.c_str()));
        dirty_ = true;
    }} else {{
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }}
}}
... other functions

After refactoring:
// Settings.h
#ifndef SETTINGS_H
#define SETTINGS_H

#include <string>
#include <memory>
#include "INvsStorage.h"
#include "ILogger.h"

class Settings {{
public:
    Settings(const std::string& ns, bool read_write = false);
    ~Settings();

    std::string GetString(const std::string& key, const std::string& default_value);
    void SetString(const std::string& key, const std::string& value);
    
    int32_t GetInt(const std::string& key, int32_t default_value);
    void SetInt(const std::string& key, int32_t value);
    
    void EraseKey(const std::string& key);
    void EraseAll();

private:
    std::unique_ptr<INvsStorage> nvs_storage_;
    std::unique_ptr<ILogger> logger_;
    std::string ns_;
    bool read_write_;
    bool dirty_;
}};

#endif // SETTINGS_H

// Settings.cc
#include "Settings.h"
#include "EspNvsStorage.h"
#include "EspLogger.h"
#include <esp_log.h>
#include <memory>
#include <algorithm>

#define TAG "Settings"

Settings::Settings(const std::string& ns, bool read_write)
            : nvs_storage_(std::make_unique<EspNvsStorage>(ns, read_write)),
              logger_(std::make_unique<EspLogger>()),
              ns_(ns),
              read_write_(read_write),
              dirty_(false) {{
}}
...
void Settings::SetString(const std::string& key, const std::string& value) {{
    if (!nvs_storage_) {{
        if (logger_) {{
            logger_->LogWarning(TAG, "NVS storage not initialized");
        }}
        return;
    }}
    
    if (read_write_) {{
        nvs_storage_->SetString(key, value);
        dirty_ = true;
    }} else {{
        if (logger_) {{
            logger_->LogWarning(TAG, "Namespace " + ns_ + " is not open for writing");
        }}
    }}
}}
... other functions

Please first output the intermediate analysis process and then output your results in the following YAML format inside the ```yaml ``` mark:
nodes: current module information split into header and source files
   - id: {name}.h (for header file)
   - type: "header"
   - code: |
     Complete header file content with all necessary #include statements, class declaration, and method signatures
   - description: Header file for {name} class containing interface declarations and dependencies

   - id: {name}.cc (for source file)  
   - type: "source"
   - code: |
     Complete source file content with all necessary #include statements and method implementations
   - description: Source file for {name} class containing method implementations using dependency injection

Current module name: {name}

Below are the provided interface modules (implementation nodes are not provided):
{nodes}

Below is the concrete header file and source file implementation of the current module:
{header}
{source}
""",

   "functionality_decompose": """As a professional software engineer, please:

1. According to the Single Responsibility Principle, classify and list the function APIs and variables implemented by the current module based on their functionality, forming decoupled functional submodules of the current module.
2. For each functional submodule, construct it as a new node and establish its association with the current module node.

Please first output the intermediate analysis process and then output your results in the following YAML format inside the ```yaml ``` mark:
nodes: node information for all sub-modules(except the current module)
   - id: decomposed sub-node name
   - type: "implementation"
   - code: |
    the detailed code implementation of the sub-node (include necessary #include statements)
   - description: Describe WHAT the code does - the functional purpose, responsibilities, and behavior, considering the context.

Below is the concrete implementation of the current module:
{refactored_node}
""",

   "dependency_propagation_decision": """You are assisting in an incremental refactoring workflow.

Current refactored file: {current_file}
Dependent file under review: {dependent_file}

The current file produced the following graph structure:
```json
{current_graph}
```

The dependent file currently has this graph representation:
```json
{dependent_graph}
```

Please determine whether the dependent file must be refactored again to stay consistent with the updated current file. Consider interface changes, dependency mismatches, or other incompatibilities.

Respond in JSON (inside ```json```), using:
- need_refactor: true | false
- updated_graph: (required when need_refactor is true) the complete graph JSON for the newly refactored dependent file.
""",

   "one_round_prompt": """As an experienced software engineer, analyze the provided module based on **reusability**.

First, output your intermediate reasoning process.

Then, refactor the module based on the reusability analysis and decide how to align with the output format. After refactoring the provided module, retain its original interfaces.

Finally output your final results in the following YAML format (wrapped in ```yaml```):
```yaml
nodes:
  - id: <header_name>.h
    type: header
    description: <Describe WHAT the header does - functional purpose and responsibilities>
    code: |
      <Complete header declaration with all necessary #include statements>
  
  - id: <source_name>.cc
    type: source
    description: <Describe WHAT the source does - functional purpose and responsibilities>
    code: |
      <Complete source code with runnable code and all necessary #include statements>
  ...
```

**REFACTORING EXAMPLE**:

Example 1: Settings Module Refactoring

Before refactoring:
// settings.h
#ifndef SETTINGS_H
#define SETTINGS_H

#include <string>
#include <nvs_flash.h>

class Settings {{
public:
    Settings(const std::string& ns, bool read_write = false);
    ~Settings();
    std::string GetString(const std::string& key, const std::string& default_value = "");
    void SetString(const std::string& key, const std::string& value);
    // ... other methods

private:
    std::string ns_;
    nvs_handle_t nvs_handle_ = 0;  // Direct dependency on nvs_handle_t
    bool read_write_ = false;
    bool dirty_ = false;
}};
#endif

// settings.cc
#include "settings.h"
#include <esp_log.h>
#include <nvs_flash.h>

Settings::Settings(const std::string& ns, bool read_write) : ns_(ns), read_write_(read_write) {{
    nvs_open(ns.c_str(), read_write_ ? NVS_READWRITE : NVS_READONLY, &nvs_handle_);
}}

void Settings::SetString(const std::string& key, const std::string& value) {{
    if (read_write_) {{
        ESP_ERROR_CHECK(nvs_set_str(nvs_handle_, key.c_str(), value.c_str()));
        dirty_ = true;
    }} else {{
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }}
}}
// ... other implementations

After refactoring (expected output):

```yaml
nodes:
  - id: EspNvsStorage.h
    type: header
    description: Interface for non-volatile storage operations, providing abstract methods for string and integer storage/retrieval
    code: |
      #ifndef ESP_NVS_STORAGE_H
      #define ESP_NVS_STORAGE_H
      
      #include <string>
      
      class EspNvsStorage {{
      public:
          std::string GetString(const std::string& key, const std::string& default_value = "");
          void SetString(const std::string& key, const std::string& value);
          int32_t GetInt(const std::string& key, int32_t default_value = 0);
          void SetInt(const std::string& key, int32_t value);
          void EraseKey(const std::string& key);
          void EraseAll();
      }};
      
      #endif // ESP_NVS_STORAGE_H

  - id: EspNvsStorage.cc
    type: source
    description: ESP-IDF NVS storage implementation providing concrete storage operations using ESP32 non-volatile storage
    code: |
      #include "EspNvsStorage.h"
      #include <string>
      #include <nvs_flash.h>
      EspNvsStorage::EspNvsStorage(const std::string& ns, bool read_write = false) : ns_(ns), read_write_(read_write) {{
          nvs_open(ns.c_str(), read_write_ ? NVS_READWRITE : NVS_READONLY, &nvs_handle_);
      }}
      EspNvsStorage::~EspNvsStorage() {{
          if (nvs_handle_ != 0) {{
              if (read_write_ && dirty_) {{
                  ESP_ERROR_CHECK(nvs_commit(nvs_handle_));
              }}
              nvs_close(nvs_handle_);
          }}
      }}
      ... other implementations


  - id: EspLogger.h
    type: header
    description: Interface for logging operations, providing abstract methods for different log levels
    code: |
      #ifndef ESP_LOGGER_H
      #define ESP_LOGGER_H
      
      #include <string>
      
      class EspLogger {{
      public:
          void LogWarning(const std::string& tag, const std::string& message);
          void LogError(const std::string& tag, const std::string& message);
          void LogInfo(const std::string& tag, const std::string& message);
      }};
      
      #endif // ESP_LOGGER_H

  - id: EspLogger.cc
    type: source
    description: ESP-IDF logger implementation providing concrete logging operations using ESP32 logging framework
    code: |
      #include "EspLogger.h"
      #include <string>
      #include <esp_log.h>
      EspLogger::EspLogger() {{
      }}
      void EspLogger::LogWarning(const string& tag, const string& message) {{
        ESP_LOGW(tag.c_str(), "%s", message.c_str());
      }}

      ... other implementations

  - id: settings.h
    type: header
    description: Header file for Settings class containing interface declarations and dependencies using dependency injection
    code: |
      #ifndef SETTINGS_H
      #define SETTINGS_H
      
      #include <string>
      #include <memory>
      #include "EspNvsStorage.h"
      #include "EspLogger.h"
      
      class Settings {{
      public:
          Settings(const std::string& ns, bool read_write = false);
          ~Settings();
          
          std::string GetString(const std::string& key, const std::string& default_value);
          void SetString(const std::string& key, const std::string& value);
          int32_t GetInt(const std::string& key, int32_t default_value);
          void SetInt(const std::string& key, int32_t value);
          void EraseKey(const std::string& key);
          void EraseAll();
          
      private:
          std::unique_ptr<EspNvsStorage> nvs_storage_;  // Dependency injection 
          std::unique_ptr<EspLogger> logger_;            // Dependency injection
          std::string ns_;
          bool read_write_;
          bool dirty_;
      }};
      
      #endif // SETTINGS_H

  - id: settings.cc
    type: source
    description: Source file for Settings class containing method implementations using dependency injection
    code: |
      #include "settings.h"
      #include "EspNvsStorage.h"
      #include "EspLogger.h"
      #include <memory>
      
      Settings::Settings(const std::string& ns, bool read_write)  // keep the original interface
              : nvs_storage_(std::make_unique<EspNvsStorage>(ns, read_write)),
                logger_(std::make_unique<EspLogger>()),
                ns_(ns),
                read_write_(read_write),
                dirty_(false) {{
      }}
      
      Settings::~Settings() = default;  // keep the original interface
      
      std::string Settings::GetString(const std::string& key, const std::string& default_value) {{
          if (!nvs_storage_) {{
              if (logger_) {{
                  logger_->LogWarning("Settings", "NVS storage not initialized");
              }}
              return default_value;
          }}
          return nvs_storage_->GetString(key, default_value);
      }}
      
      void Settings::SetString(const std::string& key, const std::string& value) {{
          if (!nvs_storage_) {{
              if (logger_) {{
                  logger_->LogWarning("Settings", "NVS storage not initialized");
              }}
              return;
          }}
          
          if (read_write_) {{
              nvs_storage_->SetString(key, value);
              dirty_ = true;
          }} else {{
              if (logger_) {{
                  logger_->LogWarning("Settings", "Namespace " + ns_ + " is not open for writing");
              }}
          }}
      }}
      
      // ... other method implementations
```

Here are the input parameters:

Current module name: {name}

Header file:
{header}

Source file:
{source}
""",

   "single_responsibility": """As a professional software engineer, please refactor the provided module according to the following rules:
1. First, analyze whether the current module seriously violates the Single Responsibility Principle. Only perform a refactor if there is a serious violation and the code has a large content and is a high-level complex module rather than a low-level implementation module. Otherwise, output the original module code as is.
2. If refactoring is performed, generate a header file and a source file for each sub-module. Based on these sub-modules, generate the corresponding original module.
3. Reference interfaces are the header files of the modules that the current module depends on before refactoring, you need to use these reference interfaces to refactor the current module.
4. Add a comment in the code to explain the functionality of the other used modules. 

Please first output your intermediate analysis process explaining how you identified different responsibilities. Then, according to the analysis results, taking action exactly.

Output your final results in the following YAML format (wrapped in ```yaml```):
```yaml
nodes:
  - id: <component_name>.h
    type: header
    description: <Describe WHAT the component does - its single responsibility and purpose>
    code: |
      <Complete header file with comments>
  
  - id: <component_name>.cc
    type: source
    description: <Describe WHAT the source implements - the single responsibility>
    code: |
      // Add comments explaining the interactions between the source code and other modules
      <Complete source file with comments>
```

**INPUT PARAMETERS**:

Current module name: {name}

Header file:
{header}

Source file:
{source}

Reference interfaces (optional):
{reference_interfaces}
"""
,
   "interface_extraction": """
   As a professional software engineer, please extract the interface and give explanation of the provided code.

output example:
- virtual void ShowNotification(const std::string &notification, int duration_ms = 3000) - Display notification message (std::string version), default duration is 3 seconds
- ...

   **INPUT PARAMETERS**:
   header:
   {header}
   Code:
   {code}
   """
}