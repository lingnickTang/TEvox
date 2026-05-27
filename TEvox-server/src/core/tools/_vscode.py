import requests

from src.utils.log import logger


class VSCodeClient:
    def __init__(self, base_url="http://localhost:6789"):
        """
        Initialize VSCode API client
        :param base_url: API server address
        """
        self.base_url = base_url.rstrip("/")

    def open_file(self, file_path: str) -> str:
        """
        Open file in the editor
        :param file_path: Path to the file
        :return: Success message or error message
        """
        logger.info(f"Opening file: {file_path}")
        response = requests.post(
            f"{self.base_url}/workspace/openFile", json={"filePath": file_path}
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to open file: {response.text}")

    def close_file(self, file_path: str) -> str:
        """
        Close file in the editor
        :param file_path: Path to the file
        :return: Success message or error message
        """
        logger.info(f"Closing file: {file_path}")
        response = requests.post(
            f"{self.base_url}/workspace/closeFile", json={"filePath": file_path}
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to close file: {response.text}")

    def write_file(
        self,
        file_path: str,
        content: str,
        start_line: int = 1,
        end_line: int = -1,
        edit_type: str = "replace",
    ) -> str:
        """
        Write content to file
        :param file_path: Path to the file
        :param content: Content to write
        :param start_line: Start line number to write
        :param end_line: End line number to write
        :param edit_type: Edit type, insert or replace
        :return: Success message or error message
        """
        logger.info(f"Writing to file: {file_path}")
        response = requests.post(
            f"{self.base_url}/workspace/writeFile",
            json={
                "filePath": file_path,
                "newText": content,
                "startLine": int(start_line),
                "endLine": int(end_line),
                "editType": edit_type,
            },
        )
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Failed to write to file: {response.text}")

    def rename_path(self, old_path: str, new_path: str) -> str:
        """
        Rename a file or directory from old_path to new_path.
        :param old_path: The original file or directory path.
        :param new_path: The new target file or directory path.
        :return: A success message or error message.
        """
        logger.info(f"Renaming path from {old_path} to {new_path}")
        response = requests.post(
            f"{self.base_url}/workspace/renamePath",
            json={"oldPath": old_path, "newPath": new_path},
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to rename {old_path} to {new_path}: {response.text}")

    def delete_path(self, path: str) -> str:
        """
        Delete file or directory
        :param path: Path to file or directory
        :return: Success message or error message
        """
        logger.info(f"Deleting path: {path}")
        response = requests.delete(
            f"{self.base_url}/workspace/deleteFileOrDirectory", params={"path": path}
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to delete path: {response.text}")

    def get_directory_files(self, path: str, recursive: str = "false") -> str:
        """
        Get the files in a directory
        :param path: The path to the directory to read. Must be an absolute or workspace-relative path.
        :return: The files in the directory in JSON format, or an error message if an error occurs during directory reading.
        """
        logger.info(f"Getting the files in a directory: {path}")
        response = requests.get(
            f"{self.base_url}/workspace/getDirectoryFiles",
            params={"path": path, "recursive": recursive},
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to get directory files: {response.text}")

    def get_all_open_text_documents(self) -> str:
        """
        Get all open text documents in the editor
        :return: The list of open text documents string, or error message if failed
        """
        logger.info(f"Getting all open text documents in the editor")
        response = requests.get(f"{self.base_url}/workspace/getAllOpenTextDocuments")
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to get all open text documents: {response.text}")

    def close_all_open_text_documents(self) -> str:
        """
        Close all open text documents in the editor
        :return: Success message if successful, or raises Exception if failed
        """
        logger.info("Closing all open text documents in the editor")
        response = requests.post(f"{self.base_url}/workspace/closeAllOpenTextDocuments")
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to close all open text documents: {response.text}")

    def PioBuildDevice(self) -> str:
        """
        Build device
        :return: Success message or error message
        """
        logger.info(f"Building device")
        response = requests.post(f"{self.base_url}/platformio/buildDevice")
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to build device: {response.text}")

    def PioUploadMonitorDevice(self) -> str:
        """
        Upload and monitor device
        :return: Success message or error message
        """
        logger.info(f"Uploading and monitoring device")
        response = requests.post(f"{self.base_url}/platformio/uploadMonitorDevice")
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to upload and monitor device: {response.text}")

    def PioRunTestCases(self) -> str:
        """
        运行PlatformIO测试用例
        :return: 测试结果字符串，如果失败则返回错误信息
        """
        logger.info(f"Running PlatformIO test cases")
        response = requests.post(f"{self.base_url}/platformio/runTestCases")
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to run test cases: {response.text}")

    def PioRunTestCasesWithArgs(self, filter="", ignore="") -> str:
        """
        运行PlatformIO测试用例, 支持传入过滤和忽略参数
        :param filter: 测试过滤参数，将作为 -f 后面的值传入
        :param ignore: 忽略参数，将作为 -i 后面的值传入
        :return: 测试结果字符串，如果失败则返回错误信息
        """
        logger.info("Running PlatformIO test cases with arguments")
        cmd = "pio test -vvv"
        if filter:
            cmd += f" -f {filter}"
        if ignore:
            cmd += f" -i {ignore}"
        return self.executeCommandInPioTerminal(cmd)

    def executeCommandInPioTerminal(self, command_line: str) -> str:
        """
        Execute a command in the VSCode terminal
        :param command_line: Command line to execute
        :return: Output of the command in JSON format, or error message
        """
        logger.info(f"Executing command in terminal: {command_line}")
        response = requests.post(
            f"{self.base_url}/terminal/executeCommandInPioTerminal",
            json={"commandLine": command_line},
        )
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to execute a command: {response.text}")

    def executeCommandInEspIdfTerminal(self, command_line: str) -> str:
        """
        Execute a command in the VSCode terminal
        :param command_line: Command line to execute
        :return: Output of the command in JSON format, or error message
        """
        logger.info(f"Executing command in terminal: {command_line}")
        response = requests.post(
            f"{self.base_url}/terminal/executeCommandInEspIdfTerminal",
            json={"commandLine": command_line},
        )
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to execute a command: {response.text}")

    def executeCommandInTerminal(self, command_line: str) -> str:
        """
        Execute a command in the VSCode terminal
        :param command_line: Command line to execute
        :return: Output of the command in JSON format, or error message
        """
        logger.info(f"Executing command in terminal: {command_line}")
        response = requests.post(
            f"{self.base_url}/terminal/executeCommandInTerminal",
            json={"commandLine": command_line},
        )
        if response.status_code == 200:
            return response.text
        return Exception(f"Failed to execute a command: {response.text}")

    def add_breakpoint(self, file_path: str, line_number: int) -> str:
        """
        Add a breakpoint in the VSCode debugger
        :param file_path: The path to the file to add a breakpoint
        :param line_number: The line number to add a breakpoint
        :return: A success message when the breakpoint is added, or an error message
        """
        logger.info(f"Adding breakpoint in the VSCode debugger")
        response = requests.post(
            f"{self.base_url}/debugger/add_breakpoint",
            json={"file_path": file_path, "line_number": int(line_number)},
        )
        return response.text

    def remove_breakpoint(self, file_path: str, line_number: int) -> str:
        """
        Remove a breakpoint in the VSCode debugger
        :param file_path: The path to the file to remove a breakpoint
        :param line_number: The line number to remove a breakpoint
        :return: A success message when the breakpoint is removed, or an error message
        """
        logger.info(f"Removing breakpoint in the VSCode debugger")
        response = requests.post(
            f"{self.base_url}/debugger/remove_breakpoint",
            json={"file_path": file_path, "line_number": int(line_number)},
        )
        return response.text

    def start_debugging(self) -> str:
        """
        Starting debugging using the VSCode debugger
        :return: A success message when the debug session is started, or an error message
        """
        logger.info(f"Starting debugging using the VSCode debugger")
        response = requests.post(f"{self.base_url}/debugger/start_debugging")
        return response.text

    def execute_debug_action(self, action: str) -> str:
        """
        Execute a debug action in the VSCode debugger.
        :param action: The debug action to execute. e.g. "continue", "stepOver", "stepInto", "stepOut", "pause", "stop", "restart".
        :return: A success message when the debug action is executed, or an error message
        """
        if action not in [
            "continue",
            "stepOver",
            "stepInto",
            "stepOut",
            "pause",
            "stop",
            "restart",
        ]:
            return f"Invalid debug action {action}. Legal actions are: 'continue', 'stepOver', 'stepInto', 'stepOut', 'pause', 'stop', 'restart'."
        logger.info(f"Executing debug action in the VSCode debugger")
        response = requests.post(
            f"{self.base_url}/debugger/execute_debug_action",
            json={"action": action},
        )
        return response.text

    def get_paused_state(self) -> str:
        """
        Get the paused state of the debugger
        :return: A success message when the paused state is retrieved, or an error message
        """
        logger.info(f"Getting the paused state of the debugger")
        response = requests.post(f"{self.base_url}/debugger/get_paused_state")
        return response.text

    def find_references(
        self, file_path: str, line_number: int, selected_symbol: str
    ) -> str:
        """
        Find references to the selected symbol in the given file at the specified line number.
        :param file_path: The file path (absolute or relative to the workspace).
        :param line_number: The line number to find references.
        :param selected_symbol: The symbol to find references.
        :return: The references to the selected symbol.
        """
        logger.info(f"Finding references to the selected symbol in the given file")
        response = requests.get(
            f"{self.base_url}/navigation/find_references",
            json={
                "filePath": file_path,
                "lineNumber": int(line_number),
                "selectedSymbol": selected_symbol,
            },
        )
        return response.text

    def find_in_files(
        self,
        query: str,
        filesToInclude: str = "",
        filesToExclude: str = "",
        isRegex: bool = False,
        isCaseSensitive: bool = False,
        matchWholeWord: bool = False,
    ) -> str:
        """
        Find code using VSCode's find in files functionality.
        :param query: Search query.
        :param filesToInclude: Files to include (glob pattern).
        :param filesToExclude: Files to exclude (glob pattern).
        :param isRegex: Interpret query as regular expression.
        :param isCaseSensitive: Enable case sensitivity.
        :param matchWholeWord: Match whole word only.
        :return: Result of the command execution.
        """
        logger.info(f"Finding in files with query: {query}")
        payload = {
            "query": query,
            "replace": "",
            "triggerSearch": True,
            "filesToInclude": filesToInclude,
            "filesToExclude": filesToExclude,
            "isRegex": isRegex,
            "isCaseSensitive": isCaseSensitive,
            "matchWholeWord": matchWholeWord,
        }
        response = requests.post(
            f"{self.base_url}/workspace/findInFilesOfWorkspace", json=payload
        )
        if response.status_code == 200:
            return response.text
        raise Exception(f"Failed to execute find in files: {response.text}")


if __name__ == "__main__":
    # client = VSCodeClient(base_url="http://10.166.41.116:6789")
    # client = VSCodeClient(base_url="http://10.230.33.208:6789")
    client = VSCodeClient()

    # result = client.executeCommandInEspIdfTerminal("idf.py qemu monitor")
    # print("Execute command result:", result)

    # result = client.executeCommandInEspIdfTerminal("idf.py build")
    # print("Execute command result:", result)

    # result = client.executeCommandInEspIdfTerminal("idf.py flash monitor")
    # print("Execute command result:", result)

    # result = client.PioRunTestCasesWithArgs(filter="", ignore="")
    # print("Test cases with args result:", result)

    # result = client.executeCommandInPioTerminal("pio run")
    # print("Execute command result:", result)

    # result = client.executeCommandInTerminal("ls")
    # print("Execute command result:", result)

    # result = client.insert_text_to_file("src/main.c", """printf("hello world");""", 2)
    # print("Write result:", result)

    # result = client.open_file("src/main.c")
    # print("Open result:", result)

    # result = client.open_file("README")
    # print("Open result:", result)

    # result = client.close_file("src/main.c")
    # print("Close result:", result)

    # result = client.close_file("README")
    # print("Close result:", result)

    # result = client.write_file(
    #     "src/main.c", """hello world""", edit_type="insert", start_line=1
    # )
    # print("Write result:", result)

    # result = client.get_all_open_text_documents()
    # print("Get all open text documents result:", result)

    # result = client.replace_text_in_file(
    #     "src/main.c", """printf("hello world");""", 1, 2
    # )
    # print("Write result:", result)

    # result = client.read_file("src/main.c")
    # print("Read result:", result)

    # result = client.delete_path("src/file.txt")
    # print("Delete result:", result)

    # result = client.get_directory_files("/")
    # print("Get directory files result:", result)

    # result = client.find_in_files(
    #     query="camera_config_t",
    #     filesToInclude="**/*.{c,cpp,h,hpp}",
    #     filesToExclude="",
    #     isRegex=False,
    #     isCaseSensitive=False,
    #     matchWholeWord=False,
    # )
    # print("Find in files result:", result)

    # result = client.rename_path("src/main.cpp", "src/hello.txt")
    # print("Rename result:", result)

    # result = client.close_all_open_text_documents()
    # print("Close all open text documents result:", result)

    # result = client.PioBuildDevice()
    # print("Build result:", result)

    # result = client.PioRunTestCases()
    # print("Test result:", result)

    # result = client.PioUploadMonitorDevice()
    # print("Upload and monitor result:", result)

    # result = client.executeCommandInTerminal("ls")
    # print("Execute command result:", result)

    # result = client.add_breakpoint("src/main.c", 12)
    # print("Add breakpoint result:", result)

    # result = client.remove_breakpoint("src/main.c", 12)
    # print("Remove breakpoint result:", result)

    # result = client.start_debugging()
    # print("Start debugging result:", result)

    # result = client.execute_debug_action("continue")
    # print("Execute debug action result:", result)

    # result = client.execute_debug_action("stepInto")
    # print("Execute debug action result:", result)

    # result = client.execute_debug_action("stepOut")
    # print("Execute debug action result:", result)

    # result = client.execute_debug_action("stepOver")
    # print("Execute debug action result:", result)

    # result = client.execute_debug_action("stop")
    # print("Execute debug action result:", result)

    # result = client.execute_debug_action("restart")
    # print("Execute debug action result:", result)

    # result = client.get_paused_state()
    # print("Get paused state result:", result)

    # result = client.find_references(
    #     "src/main.c",
    #     15,
    #     "test2",
    # )
    # print("Find references result:", result)
