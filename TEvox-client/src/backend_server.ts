import * as cp from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';
import { getPythonEnvironment } from './tools/environment';

let pythonProcess: cp.ChildProcess | null = null;
const outputChannel = vscode.window.createOutputChannel('Backend_Service');
const SERVER_PROCESS_NAME = 'agent-server';

const LOG_DIR = path.join(os.tmpdir(), 'vscode-backend-logs');
const LOG_FILE = path.join(LOG_DIR, 'server.log');

/**
 * ensure log dir exists
 */
function ensureLogDirectory() {
    if (!fs.existsSync(LOG_DIR)) {
        fs.mkdirSync(LOG_DIR, { recursive: true });
    }
    if (!fs.existsSync(LOG_FILE)) {
        fs.writeFileSync(LOG_FILE, '');
        console.log(`Log file created at ${LOG_FILE}`);
    }
}

/**
 * check whether server process is running
 */
async function isServerRunning(): Promise<boolean> {
    return new Promise((resolve) => {
        try {
            if (os.platform() === 'win32') {
                cp.exec('tasklist', (error, stdout) => {
                    if (error) {
                        console.error('Error checking process:', error);
                        resolve(false);
                        return;
                    }
                    resolve(stdout.toLowerCase().includes(SERVER_PROCESS_NAME.toLowerCase()));
                });
            } else {
                cp.exec('ps aux', (error, stdout) => {
                    if (error) {
                        console.error('Error checking process:', error);
                        resolve(false);
                        return;
                    }
                    resolve(stdout.toLowerCase().includes(SERVER_PROCESS_NAME.toLowerCase()));
                });
            }
        } catch (error) {
            console.error('Error checking server status:', error);
            resolve(false);
        }
    });
}

/**
 * Starts the backend service by running the server.py script.
 * @returns Promise resolving to true if the service started successfully, false otherwise.
 */
export async function startBackendService(): Promise<boolean> {
    const serverRunning = await isServerRunning();
    if (serverRunning) {
        outputChannel.appendLine('Backend service is already running.');
        return true;
    }

    outputChannel.show(true);
    outputChannel.appendLine('Starting backend service...');

    return new Promise<boolean>((resolve) => {
        try {
            // Get the Python environment
            const env = getPythonEnvironment();
            const extensionPath = env.extensionPath;
            const exePath = env.exePath;

            // Set working directory to evox-client/python directory for proper module imports
            const workingDirectory = path.join(extensionPath, 'server_execute');

            ensureLogDirectory();

            let command: string;
            if (os.platform() === 'win32') {
                // Windows 上使用 >> 追加内容，使用 2>&1 将 stderr 重定向到 stdout
                command = `"${exePath}" >> "${LOG_FILE}" 2>&1`;
            } else {
                // Unix-like 系统
                command = `"${exePath}" >> "${LOG_FILE}" 2>&1`;
            }
            const options = {
                cwd: workingDirectory,
                shell: true,
                detached: true,
                // windowsHide: os.platform() === 'win32'
            };

            outputChannel.appendLine(`Executing command: ${command}`);
            outputChannel.appendLine(`Working directory: ${workingDirectory}`);
            outputChannel.appendLine(`Log file: ${LOG_FILE}\n`);

            // Start the backend service process
            pythonProcess = cp.spawn(exePath, options);

            // Stream stdout
            if (pythonProcess.stdout) {
                pythonProcess.stdout.on('data', (data) => {
                    const output = data.toString();
                    outputChannel.append(output);
                });
            }

            // Stream stderr
            if (pythonProcess.stderr) {
                pythonProcess.stderr.on('data', (data) => {
                    const output = data.toString();
                    outputChannel.appendLine(`ERROR: ${output}`);
                });
            }

            // Handle process completion
            pythonProcess.on('close', (code) => {
                outputChannel.appendLine(`\nBackend service process exited with code ${code}`);
                if (code === 0) {
                    vscode.window.showInformationMessage('Backend service started successfully');
                    resolve(true);
                } else {
                    vscode.window.showErrorMessage('Backend service failed to start');
                    resolve(false);
                }
            });
            pythonProcess.unref();

            setTimeout(async () => {
                const running = await isServerRunning();
                if (running) {
                    vscode.window.showInformationMessage('Backend service started successfully');
                    resolve(true);
                } else {
                    vscode.window.showErrorMessage('Backend service failed to start');
                    resolve(false);
                }
            }, 10000);

        } catch (error) {
            const errorMessage = `Failed to start backend service: ${error}`;
            outputChannel.appendLine(`\n${errorMessage}`);
            vscode.window.showErrorMessage(errorMessage);
            resolve(false);
        }
    });
}

export function stopBackendService(): void {
    // 记录停止时间
    if (fs.existsSync(LOG_FILE)) {
        fs.appendFileSync(LOG_FILE, `\n[${new Date().toISOString()}] Stopping server...\n`);
    }

    if (os.platform() === 'win32') {
        cp.exec(`taskkill /F /IM ${SERVER_PROCESS_NAME}.exe`);
    } else {
        cp.exec(`pkill -f ${SERVER_PROCESS_NAME}`);
    }
    console.log('Backend service stopped.');
    vscode.window.showInformationMessage('Backend service stopped.');
}

// 添加命令以查看日志
export function registerCommands(context: vscode.ExtensionContext) {
    context.subscriptions.push(
        vscode.commands.registerCommand('extension.openServerLogs', () => {
            if (fs.existsSync(LOG_FILE)) {
                vscode.workspace.openTextDocument(LOG_FILE)
                    .then(doc => vscode.window.showTextDocument(doc));
            } else {
                vscode.window.showInformationMessage('No server logs available');
            }
        })
    );
}