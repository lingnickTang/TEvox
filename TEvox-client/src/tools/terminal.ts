import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';


const EspIdfTerminalName = 'ESP-IDF Terminal';
const PlatformIOTerminalName = 'PlatformIO CLI';
const CustomShellTerminalName = 'CustomShell';

function findTerminalByName(name: string): vscode.Terminal | undefined {
    return vscode.window.terminals.find((term) => term.name === name);
}

async function getPlatformIOTerminal(): Promise<vscode.Terminal> {
    let terminal = findTerminalByName(PlatformIOTerminalName);
    if (terminal) {
        return terminal;
    }

    await vscode.commands.executeCommand('platformio-ide.openPIOCoreCLI');
    await new Promise((resolve) => setTimeout(resolve, 5000));

    terminal = findTerminalByName(PlatformIOTerminalName);
    if (terminal) {
        return terminal;
    }

    throw new Error('Failed to open PlatformIO Terminal.');
}

async function getCustomShellTerminal(): Promise<vscode.Terminal> {
    let terminal = findTerminalByName(CustomShellTerminalName);
    if (terminal) {
        return terminal;
    }

    terminal = vscode.window.createTerminal(CustomShellTerminalName);
    await new Promise((resolve) => setTimeout(resolve, 5000));

    if (terminal.shellIntegration) {
        return terminal;
    }

    throw new Error('Failed to open CustomShell Terminal.');
}

async function getEspIdfTerminal(): Promise<vscode.Terminal> {
    let terminal = findTerminalByName(EspIdfTerminalName);
    if (terminal) {
        return terminal;
    }

    await vscode.commands.executeCommand('espIdf.createIdfTerminal');
    await new Promise((resolve) => setTimeout(resolve, 60000));

    terminal = findTerminalByName(EspIdfTerminalName);
    if (terminal) {
        return terminal;
    }

    throw new Error('Failed to open ESP-IDF Terminal.');
}

export async function executeCommandInTerminal(terminal: vscode.Terminal, commandLine: string, timeout: number): Promise<string> {
    let output = '';
    terminal.show();

    if (terminal.shellIntegration) {
        const timeoutPromise = new Promise((resolve) => { setTimeout(resolve, timeout); });

        const readStream = new Promise((resolve) => {
            (async () => {
                let timeoutId: NodeJS.Timeout;
                const startTimer = () => {
                    clearTimeout(timeoutId);
                    timeoutId = setTimeout(() => { setTimeout(resolve, 0); }, 30000);
                };

                const command = terminal.shellIntegration!.executeCommand(commandLine);
                const stream = command.read();
                for await (const data of stream) {
                    output += data;
                    startTimer();
                }
                setTimeout(resolve, 0);
            })();
        });

        await Promise.race([readStream, timeoutPromise]);

        // 判断output的长度，如果超过，就截取后面的部分
        if (output.length > 16000) {
            output = output.slice(output.length - 16000);
        }

        terminal.sendText("\u0003"); // Ctrl+C to clear the terminal

        return output;
    }

    throw new Error('Shell integration is not available in this terminal.');
}


export async function executeCommandInTerminalWithRedirection(terminal: vscode.Terminal, commandLine: string, timeout: number): Promise<string> {
    let output = '';
    terminal.show();

    terminal.sendText("\u0003"); // Ctrl+C to clear the terminal

    const outputDir = path.join(os.homedir(), 'vscode-terminal-output');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    const outputFile = path.join(outputDir, 'vscode-cmd-output.txt');
    const triggerFile = path.join(outputDir, 'vscode-cmd-trigger.txt');

    try {
        if (fs.existsSync(outputFile)) {
            fs.writeFileSync(outputFile, '');
        }
    } catch (error) {
        // Ignore errors if files don't exist
    }

    terminal.sendText(`${commandLine} 2>&1 | tee "${outputFile}"; echo done > "${triggerFile}"`);

    const timeoutPromise = new Promise((resolve) => { setTimeout(resolve, timeout); });

    const readStream = new Promise((resolve) => {
        (async () => {
            let flag = false;
            const watcher = fs.watch(triggerFile, (eventType) => {
                if (eventType === 'change') {
                    watcher.close();
                    flag = true;
                }
            });
            while (1) {
                if (flag) {
                    setTimeout(resolve, 0);
                    break;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
            }
        })();
    });

    const inactivityPromise = new Promise((resolve) => {
        let timeoutId: NodeJS.Timeout;
        let watcher: fs.FSWatcher;
 
        const startTimer = () => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                watcher?.close();
                setTimeout(resolve, 0);
            }, 300000);
        };

        try {
            watcher = fs.watch(outputFile, (eventType) => {
                console.log("Output file event detected:", eventType);
                if (eventType === 'change') {
                    startTimer();
                }
            });
            startTimer();
        } catch (err) {
            startTimer();
        }
    });

    await Promise.race([readStream, timeoutPromise, inactivityPromise]);

    output = fs.readFileSync(outputFile, 'utf-8');

    // 判断output的长度，如果超过，就截取后面的部分
    if (output.length > 16000) {
        output = output.slice(output.length - 16000);
    }

    return output;
}

export async function runPlatformIOCommand(command: string, timeout: number): Promise<string> {
    const terminal = await getPlatformIOTerminal();
    return await executeCommandInTerminal(terminal, command, timeout);
}

export async function runCustomShellCommand(command: string, timeout: number): Promise<string> {
    const terminal = await getCustomShellTerminal();
    return await executeCommandInTerminal(terminal, command, timeout);
}

export async function runEspIdfCommand(command: string, timeout: number): Promise<string> {
    const terminal = await getEspIdfTerminal();
    return await executeCommandInTerminalWithRedirection(terminal, command, timeout);
}