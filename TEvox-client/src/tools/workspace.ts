import * as vscode from 'vscode';
import * as os from 'os';

interface FileContent {
    filePath: string;
    content: string;
}

interface DiffContent {
    msg: string
    filePath: string;
    oldText: string;
    newText: string;
}

export function getFileUri(filePath: string): vscode.Uri {
    let fileUri: vscode.Uri;
    if(os.platform() === 'win32'){
        if (filePath.indexOf(":") === -1) {
            const workspaceUri = vscode.workspace.workspaceFolders![0].uri;
            fileUri = vscode.Uri.joinPath(workspaceUri, filePath);
        } else {
            fileUri = vscode.Uri.file(filePath);
        }
    } else {
        // 非 Windows 系统的处理逻辑
        if (filePath.startsWith('/')) {
            // 如果是绝对路径，直接创建 Uri
            fileUri = vscode.Uri.file(filePath);
        } else {
            // 如果是相对路径，则基于工作区路径
            const workspaceUri = vscode.workspace.workspaceFolders![0].uri;
            fileUri = vscode.Uri.joinPath(workspaceUri, filePath);
        }
    }
    
    return fileUri;
}

function getFileContentWithLineNumbers(document: vscode.TextDocument): string {
    let content = '';
    for (let i = 0; i < document.lineCount; i++) {
        content += `${i + 1}: ${document.lineAt(i).text}\n`;
    }
    return "<file path=" + document.uri.fsPath + ">\n" + content + "</file>";
}

export async function openFile(filePath: string): Promise<vscode.TextDocument> {
    const fileUri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(fileUri);
    await vscode.window.showTextDocument(document, { preview: false });
    return document;
}

export async function closeFile(filePath: string): Promise<void> {
    await openFile(filePath);
    await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
}

export async function readFile(document: vscode.TextDocument, withLineNumber: boolean): Promise<string> {
    const content = withLineNumber ? getFileContentWithLineNumbers(document) : document.getText();
    return content;
}

export async function writeFile(filePath: string, startLine: number, endLine: number, newText: string, editType: string): Promise<DiffContent> {
    const fileUri = getFileUri(filePath);

    let fileExists = true;
    try {
        await vscode.workspace.fs.stat(fileUri);
    } catch {
        await vscode.workspace.fs.writeFile(fileUri, new Uint8Array());
        fileExists = false;
    }

    const document = await vscode.workspace.openTextDocument(fileUri);
    await vscode.window.showTextDocument(document, { preview: false });
    const edit = new vscode.WorkspaceEdit();
    const oldText = getFileContentWithLineNumbers(document);

    if (startLine === -1) {
        startLine = document.lineCount;
    }

    if (endLine === -1) {
        endLine = document.lineCount;
    }

    if (!fileExists) {
        edit.insert(document.uri, new vscode.Position(0, 0), newText);
    } else {
        if (editType === "replace") {
            edit.replace(document.uri, new vscode.Range(startLine - 1, 0, endLine, 0), newText);
        }
        else if (editType === "insert") {
            edit.insert(document.uri, new vscode.Position(startLine - 1, 0), newText);
        }
    }

    const success = await vscode.workspace.applyEdit(edit);
    if (!success) {
        throw new Error(`Failed to apply edit to file '${fileUri.fsPath}'`);
    }

    await document.save();

    await vscode.commands.executeCommand('editor.action.formatDocument');

    return { msg: "", filePath: fileUri.fsPath, oldText: oldText, newText: getFileContentWithLineNumbers(document) };
}

export async function deleteFileOrDirectory(path: string): Promise<void> {
    const uri = getFileUri(path);
    await vscode.workspace.fs.delete(uri, { recursive: true, useTrash: true });
}

export async function getDirectoryFiles(path: string, recursive: boolean): Promise<string> {
    const uri = getFileUri(path);
    let files = await vscode.workspace.fs.readDirectory(uri);
    return "<directory path=" + uri.fsPath + ">\n" + await renderDirectoryTree(uri, files, 0, recursive) + "</directory>";
}

async function renderDirectoryTree(uri: vscode.Uri, files: [string, vscode.FileType][], level: number, recursive: boolean): Promise<string> {
    let tree = '';

    for (let i = 0; i < files.length; i++) {
        const [name, type] = files[i];

        const prefix = i === files.length - 1 ? '└─ ' : '├─ ';
        let item = `${'│  '.repeat(level)}${prefix}${name}`;
        if (type === vscode.FileType.Directory) {
            item += '/';
        }
        tree += item + '\n';


        if (type === vscode.FileType.Directory && recursive) {
            if (name.startsWith('.')) {
                continue;
            }

            if (name === "build") {
                continue;
            }

            const directoryUri = vscode.Uri.joinPath(uri, name);
            const children = await vscode.workspace.fs.readDirectory(directoryUri);

            // if (children.length === 0 || children.length > 3) {
            //     continue;
            // }

            if (children.length === 0) {
                continue;
            }

            tree += await renderDirectoryTree(directoryUri, children, level + 1, recursive);
        }
    }

    return tree;
}

export async function getAllOpenTextDocuments(): Promise<FileContent[]> {
    let fileContents: FileContent[] = [];
    const allTabs = vscode.window.tabGroups.all.flatMap(({ tabs }) => tabs);

    for (const tab of allTabs) {
        if (typeof tab.input === 'object' && tab.input !== null) {
            if ('uri' in tab.input) {
                const fileUri = tab.input.uri as vscode.Uri;
                const document = await vscode.workspace.openTextDocument(fileUri);
                fileContents.push({
                    filePath: fileUri.fsPath,
                    content: getFileContentWithLineNumbers(document)
                });
            }
        }
    }

    return fileContents;
}

export async function getAllOpenTextDocumentsString(): Promise<string> {
    const files = await getAllOpenTextDocuments();
    return files.map(file => file.content).join("\n\n");
}

export async function closeAllOpenTextDocuments(): Promise<void> {
    const allTabs = vscode.window.tabGroups.all.flatMap(({ tabs }) => tabs);

    for (const tab of allTabs) {
        try {
            await vscode.window.tabGroups.close(tab);
        } catch (error) {
            console.error(`Failed to close tab: ${tab.label}`, error);
        }
    }
}

export async function renamePath(oldPath: string, newPath: string): Promise<void> {
    const oldUri = getFileUri(oldPath);
    const newUri = getFileUri(newPath);
    try {
        await vscode.workspace.fs.rename(oldUri, newUri, { overwrite: true });
    } catch (error) {
        throw error;
    }
}