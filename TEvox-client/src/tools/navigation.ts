import * as vscode from 'vscode';

interface Reference {
    path: string;
    line: number;
    code: string;
}

/**
 * Finds references to the selected symbol in the given file at the specified line number.
 * @param filePath - The file path (absolute or relative to the workspace).
 * @param lineNumber - The line number to find references.
 * @param selectedSymbol - The symbol to find references.
 * @returns A promise that resolves with the references.
 */
export async function findReferences(filePath: string, lineNumber: number, selectedSymbol: string): Promise<Reference[]> {
    let fileUri: vscode.Uri;
    if (filePath.indexOf(":") === -1) {
        const workspaceUri = vscode.workspace.workspaceFolders![0].uri;
        fileUri = vscode.Uri.joinPath(workspaceUri, filePath);
    } else {
        fileUri = vscode.Uri.file(filePath);
    }

    const document = await vscode.workspace.openTextDocument(fileUri);

    let line: vscode.TextLine;
    try {
        line = document.lineAt(lineNumber);
    } catch (error) {
        throw new Error(`Line number ${lineNumber + 1} not found in file '${filePath}'. Legal values are between 1 and ${document.lineCount}.`);
    }

    const character = line.text.indexOf(selectedSymbol);
    if (character === -1) {
        throw new Error(`Symbol '${selectedSymbol}' not found in line ${lineNumber + 1}.`);
    }

    const currentSymbol = document.getWordRangeAtPosition(new vscode.Position(lineNumber, character));
    const references = await vscode.commands.executeCommand<vscode.Location[]>('vscode.executeReferenceProvider', document.uri, currentSymbol!.start);
    if (!references) {
        return [];
    }

    const result: Reference[] = [];
    const referencesWithCode = await Promise.all(
        references.map(async (reference) => {
            const refDoc = await vscode.workspace.openTextDocument(reference.uri);
            return {
                path: reference.uri.fsPath,
                line: reference.range.start.line + 1,
                code: refDoc.lineAt(reference.range.start.line).text,
            };
        })
    );

    return referencesWithCode;
}