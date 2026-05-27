"""
ESP-IDF终端管理器
基于Windows PowerShell配置的ESP-IDF v5.3.3终端管理
"""

import subprocess
import os
import sys
import time
from pathlib import Path
from typing import Tuple, Optional, List
import logging

# 设置日志
logger = logging.getLogger(__name__)


class ESPIDFTerminal:
    """ESP-IDF终端管理器 - 基于Windows PowerShell配置"""
    
    def __init__(self, 
                 esp_idf_path,
                 init_script_path,
                 project_path):
        """
        初始化ESP-IDF终端
        
        Args:
            esp_idf_path: ESP-IDF安装路径
            init_script_path: ESP-IDF初始化脚本路径
            project_path: ESP-IDF项目路径
        """
        self.esp_idf_path = esp_idf_path
        self.init_script_path = init_script_path
        self.project_path = project_path or os.getcwd()
        
        # 验证路径
        if not os.path.exists(self.esp_idf_path):
            raise ValueError(f"ESP-IDF路径不存在: {self.esp_idf_path}")
        
        if not os.path.exists(self.init_script_path):
            raise ValueError(f"ESP-IDF初始化脚本不存在: {self.init_script_path}")
        
        if not os.path.exists(self.project_path):
            raise ValueError(f"项目路径不存在: {self.project_path}")
        
        # 设置idf.py路径
        self.idf_py_path = os.path.join(self.esp_idf_path, "tools", "idf.py")
        print("设置idf.py路径:", self.idf_py_path)
        print(f"ESP-IDF路径: {self.esp_idf_path}")
        print(f"初始化脚本: {self.init_script_path}")
        print(f"项目路径: {self.project_path}")
        print(f"idf.py路径: {self.idf_py_path}")
    
    def _setup_environment(self) -> dict:
        """设置ESP-IDF环境变量"""
        env = os.environ.copy()
        
        # 设置ESP-IDF相关环境变量
        env['IDF_PATH'] = self.esp_idf_path
        
        # 添加ESP-IDF工具到PATH
        tools_path = os.path.join(self.esp_idf_path, "tools")
        python_path = os.path.join(self.esp_idf_path, "python_env", "idf5.3_py3.11_env", "Scripts")
        
        # 更新PATH环境变量
        current_path = env.get('PATH', '')
        new_paths = [
            tools_path,
            python_path,
            os.path.join(self.esp_idf_path, "components", "esptool_py", "esptool"),
            os.path.join(self.esp_idf_path, "components", "app_update"),
        ]
        
        for path in new_paths:
            if os.path.exists(path) and path not in current_path:
                current_path = f"{path};{current_path}"
        
        env['PATH'] = current_path
        
        # 设置Python路径
        python_env_path = os.path.join(self.esp_idf_path, "python_env", "idf5.3_py3.11_env")
        if os.path.exists(python_env_path):
            env['PYTHONPATH'] = python_env_path
        
        return env
    
    def _get_powershell_command(self, command: str) -> list:
        """构建PowerShell命令"""
        # 使用PowerShell执行ESP-IDF命令，设置正确的编码
        ps_command = f"""
        # 设置控制台编码为UTF-8
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8
        
        # 导入ESP-IDF环境
        & "{self.init_script_path}" -IdfId esp-idf-6af48ca668531ae4984a50282726e819
        
        # 切换到项目目录
        Set-Location "{self.project_path}"
        
        # 执行ESP-IDF命令并检查结果
        {command}
        $exitCode = $LASTEXITCODE
        
        # 如果命令失败，以相同的退出码退出
        if ($exitCode -ne 0) {{
            exit $exitCode
        }}
        
        exit 0
        """
        
        return [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-NoProfile",
            "-Command", ps_command
        ]
    
    def _read_build_logs(self) -> str:
        """读取build日志文件"""
        try:
            log_dir = os.path.join(self.project_path, "build", "log")
            if not os.path.exists(log_dir):
                return ""
            
            # 查找最新的日志文件
            log_files = []
            for file in os.listdir(log_dir):
                if file.startswith("idf_py_stdout_output_"):
                    log_files.append(file)
            
            if not log_files:
                return ""
            
            # 按修改时间排序，获取最新的
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
            latest_log = os.path.join(log_dir, log_files[0])
            
            # 读取日志文件内容
            with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            return content
            
        except Exception as e:
            logger.error(f"读取build日志失败: {str(e)}")
            return ""
    
    def execute_command(self, command: str, timeout: int = 300, use_powershell: bool = True) -> Tuple[bool, str, str]:
        """
        执行ESP-IDF命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            use_powershell: 是否使用PowerShell执行（推荐）
            
        Returns:
            Tuple[success, stdout, stderr]
        """
        try:
            if use_powershell:
                # 使用PowerShell方式执行
                full_command = self._get_powershell_command(command)
                print(f"执行PowerShell命令: {full_command}")
            else:
                # 使用直接subprocess方式
                env = self._setup_environment()
                
                if command.startswith("idf.py"):
                    full_command = [sys.executable, self.idf_py_path] + command.split()[1:]
                else:
                    full_command = command.split()
                
                print(f"执行命令: {' '.join(full_command)}")
                print(f"工作目录: {self.project_path}")
            
            # 执行命令，设置正确的编码
            if use_powershell:
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',  # 明确指定UTF-8编码
                    errors='replace',  # 遇到编码错误时用替换字符代替
                    timeout=timeout,
                    cwd=self.project_path
                )
            else:
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',  # 明确指定UTF-8编码
                    errors='replace',  # 遇到编码错误时用替换字符代替
                    timeout=timeout,
                    env=env,
                    cwd=self.project_path
                )
            
            success = result.returncode == 0
            print(f"命令执行完成，成功: {success}")
            
            # 如果stdout为空但stderr有内容，将stderr内容合并到stdout
            stdout_content = result.stdout if result.stdout else ""
            stderr_content = result.stderr if result.stderr else ""
            
            # 对于build命令，如果输出为空，尝试读取日志文件
            if not stdout_content and command.startswith("idf.py build"):
                stdout_content = self._read_build_logs()
            
            return success, stdout_content, stderr_content
            
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时 ({timeout}秒)")
            # 即使超时，也尝试读取日志文件
            log_content = ""
            if command.startswith("idf.py build"):
                log_content = self._read_build_logs()
            return False, log_content, f"命令执行超时 ({timeout}秒)"
        except Exception as e:
            logger.error(f"执行错误: {str(e)}")
            # 即使出错，也尝试读取日志文件
            log_content = ""
            if command.startswith("idf.py build"):
                log_content = self._read_build_logs()
            return False, log_content, f"执行错误: {str(e)}"

    def build_flash_monitor(self, monitor_timeout: int = 60) -> Tuple[bool, str, str]:
        """编译、烧录并监控项目"""
        print("开始编译、烧录并监控项目")
        
        # 1. 编译项目
        success, stdout, stderr = self.build()
        if not success:
            logger.error(f"编译失败: {stderr}")
            return False, stdout, stderr
        
        print("编译成功，开始烧录...")
        
        # 2. 烧录固件（不包含monitor）
        success, stdout2, stderr2 = self.flash()
        if not success:
            logger.error(f"烧录失败: {stderr2}")
            return False, stdout2, stderr2
        
        print("烧录成功，开始智能监控...")
        
        # 3. 使用智能监控，检测到程序完成标志后退出
        success, stdout3, stderr3 = self.monitor_with_pattern(timeout=monitor_timeout)
        if not success:
            logger.warning(f"监控超时或被中断: {stderr3}")
            # 监控失败不应该影响整体结果，因为程序可能已经正常运行
        
        print("编译、烧录和监控完成")
        return True, stdout3, stderr3
    
    def build(self) -> Tuple[bool, str, str]:
        """编译项目"""
        command = "idf.py build"
        print(f"开始编译项目: {command}")
        return self.execute_command(command, timeout=600)
    
    def flash(self) -> Tuple[bool, str, str]:
        """烧录固件"""
        command = "idf.py flash"
        print(f"开始烧录固件: {command}")
        return self.execute_command(command, timeout=300)
    
    def _kill_process_by_pid(self, pid: int) -> None:
        """通过PowerShell命令终止占用串口的idf.py monitor相关Python进程"""
        try:
            ps_command = '''
            # 查找并终止占用串口的Python进程（通过命令行参数匹配）
            # 先获取所有正在运行的Python进程PID
            $runningPids = (Get-Process python*,pythonw* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
            
            $killedCount = 0
            # 对每个正在运行的进程，查询其命令行参数
            foreach ($runningPid in $runningPids) {
                try {
                    # 获取进程的命令行信息
                    $proc = Get-WmiObject Win32_Process -Filter "ProcessId=$runningPid" -ErrorAction SilentlyContinue
                    if ($proc) {
                        $cmdLine = $proc.CommandLine
                        # 匹配命令行中包含 idf.py monitor、idf_monitor.py 或 esp_idf_monitor 的进程
                        if ($cmdLine -and (
                            ($cmdLine -like "*idf.py*monitor*") -or
                            ($cmdLine -like "*idf_monitor*") -or
                            ($cmdLine -like "*esp_idf_monitor*")
                        )) {
                            # 再次验证进程是否还存在（双重检查）
                            $processExists = Get-Process -Id $runningPid -ErrorAction SilentlyContinue
                            if ($processExists) {
                                Stop-Process -Id $runningPid -Force -ErrorAction SilentlyContinue
                                Write-Host "已终止占用串口的Python进程 PID: $runningPid"
                                $killedCount++
                            }
                        }
                    }
                } catch {
                    # 忽略单个进程的错误，继续处理下一个
                }
            }
            
            if ($killedCount -eq 0) {
                Write-Host "未找到需要终止的进程"
            } else {
                Write-Host "总共终止了 $killedCount 个进程"
            }
            '''
            
            result = subprocess.run(
                ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60
            )
        except Exception as e:
            logger.warning(f"通过PowerShell终止进程失败: {str(e)}")
    
    def monitor_with_pattern(self, timeout: int = 60) -> Tuple[bool, str, str]:
        """监控串口，检测到特定模式后退出"""
        exit_patterns = [
                "tests completed",
                "All test cases passed",
                "Test suite completed",
                "✓ All test cases passed",
                "✗ Test case",
                # 程序异常退出模式
                "Exception occurred",
                "Fatal error",
                "Segmentation fault",
                "Stack overflow"
            ]
        
        command = "idf.py monitor"
        print(f"开始智能监控串口，检测到完成标志后退出: {command}")
        print(f"退出模式: {exit_patterns}")
        
        process = None
        process_pid = None
        
        try:
            # 使用 subprocess.Popen 而不是 run，以便实时处理输出
            process = subprocess.Popen(
                self._get_powershell_command(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=self.project_path,
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )
            
            # 获取进程PID
            process_pid = process.pid
            print(f"监控进程已启动，PID: {process_pid}")
            
            output_lines = []
            start_time = time.time()
            
            # 实时读取输出
            while True:
                # 检查超时
                if time.time() - start_time > timeout:
                    print(f"监控超时 ({timeout}秒)，强制退出")
                    # 超时时先尝试正常终止，然后使用PowerShell强制终止
                    if process.poll() is None:
                        process.terminate()
                        time.sleep(1)
                        if process.poll() is None:
                            process.kill()
                    # 使用PowerShell确保进程被终止
                    if process_pid:
                        self._kill_process_by_pid(process_pid)
                    return False, '\n'.join(output_lines), f"监控超时 ({timeout}秒)"
                
                # 检查进程是否自然结束
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    # 即使进程自然结束，也使用PowerShell确保清理
                    if process_pid:
                        self._kill_process_by_pid(process_pid)
                    return process.returncode == 0, '\n'.join(output_lines) + '\n' + stdout, stderr
                
                # 读取一行输出
                try:
                    line = process.stdout.readline()
                    if line:
                        line = line.strip()
                        output_lines.append(line)
                        print(f"Monitor: {line}")
                        
                        # 检查退出模式
                        for pattern in exit_patterns:
                            if pattern in line:
                                print(f"✓ 检测到程序完成标志: {pattern}")
                                # 给一点时间让输出完成
                                time.sleep(2)
                                
                                # 直接终止进程
                                print("检测到完成标志，终止monitor进程...")
                                if process.poll() is None:
                                    process.terminate()
                                    time.sleep(1)
                                    if process.poll() is None:
                                        process.kill()
                                # 使用PowerShell确保进程被终止
                                if process_pid:
                                    self._kill_process_by_pid(process_pid)
                                
                                return True, '\n'.join(output_lines), ""
                    else:
                        # 没有新输出，短暂等待
                        time.sleep(0.1)
                except Exception as e:
                    print(f"读取输出时出错: {e}")
                    break
            
            # 获取剩余输出
            try:
                stdout, stderr = process.communicate(timeout=5)
                # 使用PowerShell确保进程被终止
                if process_pid:
                    self._kill_process_by_pid(process_pid)
                return True, '\n'.join(output_lines) + '\n' + stdout, stderr
            except:
                # 使用PowerShell确保进程被终止
                if process_pid:
                    self._kill_process_by_pid(process_pid)
                return True, '\n'.join(output_lines), "监控正常结束"
            
        except Exception as e:
            logger.error(f"监控过程出错: {str(e)}")
            # 如果出错，也要确保进程被终止
            if process_pid:
                self._kill_process_by_pid(process_pid)
            return False, "", f"监控过程出错: {str(e)}"
    
    def monitor_with_timeout(self, timeout: int = 30) -> Tuple[bool, str, str]:
        """监控串口指定时间后自动退出"""
        return self.monitor_with_pattern(timeout=timeout)
    
    def monitor(self, port: str = None, baud: int = 115200) -> Tuple[bool, str, str]:
        """监控串口"""
        command = "idf.py monitor"
        if port:
            command += f" --port {port}"
        command += f" --baud {baud}"
        
        print(f"开始监控串口: {command}")
        return self.execute_command(command, timeout=60)
    
    def flash_monitor(self, port: str = None) -> Tuple[bool, str, str]:
        """烧录并监控"""
        command = "idf.py flash monitor"
        if port:
            command += f" --port {port}"
        
        print(f"开始烧录并监控: {command}")
        return self.execute_command(command, timeout=300)
    
    def clean(self, full: bool = False) -> Tuple[bool, str, str]:
        """清理项目"""
        command = "idf.py fullclean" if full else "idf.py clean"
        print(f"开始清理项目: {command}")
        return self.execute_command(command, timeout=120)
    
    def menuconfig(self) -> Tuple[bool, str, str]:
        """打开配置菜单"""
        command = "idf.py menuconfig"
        print(f"打开配置菜单: {command}")
        return self.execute_command(command, timeout=300)
    
    def set_target(self, target: str) -> Tuple[bool, str, str]:
        """设置目标芯片"""
        command = f"idf.py set-target {target}"
        print(f"设置目标芯片: {command}")
        return self.execute_command(command, timeout=120)
    
    def size(self) -> Tuple[bool, str, str]:
        """显示固件大小信息"""
        command = "idf.py size"
        print(f"显示固件大小: {command}")
        return self.execute_command(command, timeout=120)
    
    def size_components(self) -> Tuple[bool, str, str]:
        """显示各组件大小信息"""
        command = "idf.py size-components"
        print(f"显示组件大小: {command}")
        return self.execute_command(command, timeout=120)
    
    def size_files(self) -> Tuple[bool, str, str]:
        """显示各文件大小信息"""
        command = "idf.py size-files"
        print(f"显示文件大小: {command}")
        return self.execute_command(command, timeout=120)
    
    def erase_flash(self, port: str = None) -> Tuple[bool, str, str]:
        """擦除Flash"""
        command = "idf.py erase-flash"
        if port:
            command += f" --port {port}"
        
        print(f"擦除Flash: {command}")
        return self.execute_command(command, timeout=120)
    
    def monitor_baud(self, port: str = None, baud: int = 115200) -> Tuple[bool, str, str]:
        """以指定波特率监控"""
        command = f"idf.py monitor --baud {baud}"
        if port:
            command += f" --port {port}"
        
        print(f"监控串口: {command}")
        return self.execute_command(command, timeout=60)
    
    def get_project_info(self) -> dict:
        """获取项目信息"""
        return {
            "esp_idf_path": self.esp_idf_path,
            "init_script_path": self.init_script_path,
            "project_path": self.project_path,
            "idf_py_path": self.idf_py_path
        }


class ESPIDFProjectManager:
    """ESP-IDF项目管理器 - 提供高级项目管理功能"""
    
    def __init__(self, esp_idf_terminal: ESPIDFTerminal):
        """
        初始化项目管理器
        
        Args:
            esp_idf_terminal: ESP-IDF终端管理器实例
        """
        self.terminal = esp_idf_terminal
    
    def build_and_flash(self) -> Tuple[bool, str, str]:
        """编译并烧录项目"""
        print("开始编译并烧录项目")
        
        # 1. 编译项目
        success, stdout, stderr = self.terminal.build()
        if not success:
            logger.error(f"编译失败: {stderr}")
            return False, stdout, stderr
        
        print("编译成功，开始烧录...")
        
        # 2. 烧录固件
        success, stdout2, stderr2 = self.terminal.flash()
        if not success:
            logger.error(f"烧录失败: {stderr2}")
            return False, stdout + "\n" + stdout2, stderr + "\n" + stderr2
        
        print("编译和烧录完成")
        return True, stdout + "\n" + stdout2, stderr + "\n" + stderr2
    
    def build_flash_monitor(self, monitor_timeout: int = 60) -> Tuple[bool, str, str]:
        """编译、烧录并监控项目"""
        print("开始编译、烧录并监控项目")
        
        # 1. 编译项目
        success, stdout, stderr = self.terminal.build()
        if not success:
            logger.error(f"编译失败: {stderr}")
            return False, stdout, stderr
        
        print("编译成功，开始烧录...")
        
        # 2. 烧录固件
        success, stdout2, stderr2 = self.terminal.flash()
        if not success:
            logger.error(f"烧录失败: {stderr2}")
            return False, stdout2, stderr2
        
        print("烧录成功，开始智能监控...")
        
        # 3. 使用智能监控，检测到程序完成标志后退出
        success, stdout3, stderr3 = self.terminal.monitor_with_pattern(timeout=monitor_timeout)
        if not success:
            logger.warning(f"监控超时或被中断: {stderr3}")
            # 监控失败不应该影响整体结果，因为程序可能已经正常运行
        
        print("编译、烧录和监控完成")
        return True, stdout3, stderr3
    
    def clean_build(self) -> Tuple[bool, str, str]:
        """清理并重新编译项目"""
        print("开始清理并重新编译项目")
        
        # 1. 清理项目
        success, stdout, stderr = self.terminal.clean(full=True)
        if not success:
            logger.warning(f"清理项目时出现警告: {stderr}")
        
        # 2. 编译项目
        success, stdout2, stderr2 = self.terminal.build()
        if not success:
            logger.error(f"编译失败: {stderr2}")
            return False, stdout2, stderr2
        
        print("清理和编译完成")
        return True, stdout2, stderr2
    
    def get_build_info(self) -> Tuple[bool, str, str]:
        """获取编译信息（大小等）"""
        print("获取编译信息")
        
        # 获取基本大小信息
        success, stdout, stderr = self.terminal.size()
        if not success:
            return False, stdout, stderr
        
        # 获取组件大小信息
        success2, stdout2, stderr2 = self.terminal.size_components()
        if success2:
            stdout += "\n" + stdout2
        
        return success, stdout, stderr + stderr2


# 便捷函数
def create_esp_idf_terminal(project_path: str, 
                           esp_idf_path,
                           init_script_path) -> ESPIDFTerminal:
    """
    创建ESP-IDF终端管理器实例
    
    Args:
        project_path: ESP-IDF项目路径
        esp_idf_path: ESP-IDF安装路径
        init_script_path: ESP-IDF初始化脚本路径
    
    Returns:
        ESPIDFTerminal实例
    """
    return ESPIDFTerminal(
        esp_idf_path=esp_idf_path,
        init_script_path=init_script_path,
        project_path=project_path
    )


def create_esp_idf_project_manager(project_path: str,
                                  esp_idf_path,
                                  init_script_path) -> ESPIDFProjectManager:
    """
    创建ESP-IDF项目管理器实例
    
    Args:
        project_path: ESP-IDF项目路径
        esp_idf_path: ESP-IDF安装路径
        init_script_path: ESP-IDF初始化脚本路径
    
    Returns:
        ESPIDFProjectManager实例
    """
    terminal = create_esp_idf_terminal(project_path, esp_idf_path, init_script_path)
    return ESPIDFProjectManager(terminal)

if __name__ == "__main__":
    esp_idf_path = "F:/Espressif/frameworks/esp-idf-v5.4.2/"
    init_script_path = "F:/Espressif/Initialize-Idf.ps1"
    project_path = r"D:\Download\github\xiaozhi-esp32"
    terminal = create_esp_idf_terminal(project_path, esp_idf_path, init_script_path)

    #result = terminal.build_flash_monitor()
    result = terminal.build_flash_monitor(monitor_timeout=1)
    # result = terminal.monitor_with_pattern(timeout=1)
    print(f"Build and test result: {result}")

