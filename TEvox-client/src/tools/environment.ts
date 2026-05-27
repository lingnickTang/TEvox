import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

// Global variables for Python environment
let exePath: string = 'python';
let extensionPath: string = '';

/**
 * Initialize all paths and Python environment
 * @param extensionDir Path to the extension directory
 */
export async function initializeEnvironment(extensionDir: string): Promise<void> {
    // Get the absolute path to the extension directory
    extensionPath = extensionDir;
    if (!extensionPath) {
        // Fallback for development environment
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            throw new Error('No workspace folder found');
        }

        // Use the workspace root folder
        extensionPath = workspaceFolders[0].uri.fsPath;
        console.log('Using workspace path as fallback:', extensionPath);
        vscode.window.showWarningMessage('Using workspace path as fallback:', extensionPath);
    }

    vscode.window.showInformationMessage('Extension path:', extensionPath);

    const exeExtractPath = path.join(extensionPath, 'server_execute');

    // Initialize Python path from extracted environment
    const extractedExePath = os.platform() === 'win32'
        ? path.join(exeExtractPath, 'agent-server.exe')
        : path.join(exeExtractPath, 'agent-server');

    if (fs.existsSync(extractedExePath)) {
        exePath = extractedExePath;
        console.log('find exe path: ', exePath);
        vscode.window.showInformationMessage('find exe path: ', exePath);
    } else {
        // Fallback to system Python if extracted environment not found
        console.log('can not find agent-server executable file!');
        vscode.window.showWarningMessage('can not find agent-server executable file!');
    }

    // Log paths for debugging
    console.log('Extension Path:', extensionPath);
    console.log('Executable Path:', exePath);
}

/**
 * Get Python environment variables
 * @returns Python environment configuration
 */
export function getPythonEnvironment() {
    return {
        extensionPath,
        exePath
    };
} 