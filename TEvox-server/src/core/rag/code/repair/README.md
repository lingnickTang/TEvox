# Repairer Agent

A code repair agent that supports test generation, execution, and code repair for C++ projects.

## Features

- **Test Generation**: Generate comprehensive unit tests for C++ code
- **Test Execution**: Execute tests using ESP-IDF terminal
- **Code Repair**: Automatically repair code based on test execution results
- **Quality Validation**: Validate code quality using C++ quality analyzer

## Usage

### Basic Usage

```python
from repairer import Repairer

# Initialize repairer
repairer = Repairer(max_retries=3)

# 1. Generate test code
test_code = repairer.generate_test(source_code, description)

# 2. Execute test
execution_result = repairer.execute_test(
    test_files={"test_file.cpp": test_code},
    source_files={"source_file.cpp": source_code},
    project_path="/path/to/project"
)

# 3. Repair code if needed
if "FAILED" in execution_result:
    repaired_source = repairer.repair_code(
        source_code=source_code,
        test_code=test_code,
        execution_result=execution_result
    )
```

### Advanced Usage

```python
# Custom retry count
repairer = Repairer(max_retries=5)

# Generate test with specific description
test_code = repairer.generate_test(
    code="""
    class MyClass {
    public:
        int calculate(int x) {
            return x * 2;
        }
    };
    """,
    description="A simple calculation class"
)

# Execute with multiple files
execution_result = repairer.execute_test(
    test_files={
        "test_myclass.cpp": test_code,
        "test_utils.cpp": utility_test_code
    },
    source_files={
        "myclass.cpp": source_code,
        "utils.cpp": utility_code
    },
    project_path="/path/to/esp32/project"
)
```

## API Reference

### Repairer Class

#### `__init__(max_retries: int = 3)`
Initialize the repairer with configurable retry count.

#### `generate_test(code: str, description: str) -> str`
Generate test code for the given source code and description.
- **Raises**: `RuntimeError` if unable to generate valid test after max_retries

#### `execute_test(test_files: Dict[str, str], source_files: Dict[str, str], project_path: str) -> str`
Execute tests using ESP-IDF terminal.
- **Returns**: Execution result as string ("SUCCESS" or "FAILED" with details)

#### `repair_code(source_code: str, test_code: str, execution_result: str) -> str`
Repair source code based on execution results.
- **Returns**: Repaired source code as string
- **Raises**: `RuntimeError` if unable to repair code after max_retries

#### `_validate_code_quality(code: str) -> Tuple[bool, List[str]]`
Validate code quality and return error information.
- **Returns**: Tuple of (has_errors, error_locations)

## Error Handling

The repairer uses a retry mechanism with configurable max_retries:
- If test generation fails after max_retries, raises `RuntimeError`
- If code repair fails after max_retries, raises `RuntimeError`
- All errors are propagated without additional logging

## Dependencies

- `src.utils.Agent`
- `src.base.DefaultConfig`
- `src.core.rag.code.query.evaluator.cpp_quality_analyzer_by_package.CppCodeAnalyzerByPackage`
- `src.core.rag.code.esp_idf_terminal.ESPIDFTerminal`

## Testing

Run the test script:
```bash
python test_repairer.py
```
