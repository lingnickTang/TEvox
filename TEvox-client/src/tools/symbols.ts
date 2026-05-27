import * as vscode from 'vscode';
import { getFileUri } from "./workspace";
import { promises } from 'dns';

async function ensureAllCppExtensionsActive(): Promise<boolean> {
    const extensions = [
        'ms-vscode.cpptools',
        'ms-vscode.cpptools-extension-pack'
    ];

    for (const extId of extensions) {
        const ext = vscode.extensions.getExtension(extId);
        if (ext && !ext.isActive) {
            console.log(`⏳ Activating ${extId}...`);
            try {
                await ext.activate();
                console.log(`✅ ${extId} activated`);
                // 等待扩展完全初始化
                await new Promise(resolve => setTimeout(resolve, 2000));
            } catch (error) {
                console.log(`❌ Failed to activate ${extId}:`, error);
            }
        }
    }

    return true;
}
async function checkCppExtensions() {
    const extensions = [
        'ms-vscode.cpptools',           // Microsoft C/C++
        'llvm-vs-code-extensions.vscode-clangd',  // clangd
        'ms-vscode.cpptools-extension-pack'       // C/C++ Extension Pack
    ];

    for (const extId of extensions) {
        const ext = vscode.extensions.getExtension(extId);
        console.log(`Extension ${extId}:`, {
            installed: !!ext,
            active: ext?.isActive,
            version: ext?.packageJSON?.version
        });
    }
}

export async function recursivelyFindSymbol(document: vscode.TextDocument, symbols: vscode.DocumentSymbol[], symbolName: string, result_symbols: vscode.DocumentSymbol[], start_line: number, end_line: number):
    Promise<boolean> {
    for (const symbol of symbols) {
        if (!(symbol.range.start.line <= start_line && symbol.range.end.line >= end_line)) {
            continue;
        }
        if (symbol.kind === vscode.SymbolKind.Field || symbol.kind === vscode.SymbolKind.Variable) {
            const hover = await vscode.commands.executeCommand<vscode.Hover[]>(
                'vscode.executeHoverProvider',
                document.uri,
                symbol.selectionRange.start
            );
            var symbol_hover: string = "";
            if (hover && hover.length != 0) {
                if (typeof hover[0].contents[0] === 'string')
                    symbol_hover = hover[0].contents[0];
                else symbol_hover = hover[0].contents[0].value;
            }
            if (symbol_hover != "") {
                const pattern = new RegExp('\\b' + symbolName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b');
                if (pattern.test(symbol_hover)) {
                    result_symbols.push(symbol)
                }
            }
        } else if (symbol.kind === vscode.SymbolKind.Function || symbol.kind === vscode.SymbolKind.Method) {
            const functionBody = document.getText(symbol.range)
            const pattern = new RegExp('\\b' + symbolName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b');
            if (pattern.test(functionBody)) {
                result_symbols.push(symbol)
            }
        }
        if (symbol.children.length) {
            const found = await recursivelyFindSymbol(document, symbol.children, symbolName, result_symbols, start_line, end_line);
            if (found === false) return false;
        }

    }
    return true;
}

export async function findSymbolsReferThisSymbol(filePath: string, symbolName: string, start_line: number, end_line: number)
    : Promise<Array<{ symbolName: string, type: string }>> {
    const uri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(uri);
    const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
        'vscode.executeDocumentSymbolProvider',
        document.uri
    );
    if (!symbols) return [];
    var foundSymbols: vscode.DocumentSymbol[] = [];
    const result = await recursivelyFindSymbol(document, symbols, symbolName, foundSymbols, start_line, end_line);
    if (!result) return [];
    var result_symbols: Array<{ symbolName: string, type: string }> = [];
    for (const symbol of foundSymbols) {
        result_symbols.push({ symbolName: symbol.name, type: vscode.SymbolKind[symbol.kind] });
    }
    return result_symbols;
}

export async function getClassMembers(filePath: string, className: string
): Promise<Array<{ name: string, type: string }>> {
    const uri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(uri);
    const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
        'vscode.executeDocumentSymbolProvider',
        document.uri
    );
    if (!symbols) return [];
    const members: Array<{ name: string, type: string }> = [];
    for (const symbol of symbols) {
        if (symbol.name === className) {
            if (symbol.children) {
                for (const child of symbol.children) {
                    members.push({ name: child.name, type: vscode.SymbolKind[child.kind] });
                }
                return members;
            }
        }
    }
    return [];
}

export async function getSymbolHover(
    filePath: string,
    symbolName: string
): Promise<string | null> {
    const uri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(uri);
    const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
        'vscode.executeDocumentSymbolProvider',
        document.uri
    );
    if (!symbols) return null;
    var symbol = findSymbolByName(symbols, symbolName);
    if (!symbol) return null;
    const hover = await vscode.commands.executeCommand<vscode.Hover[]>(
        'vscode.executeHoverProvider',
        document.uri,
        symbol.selectionRange.start
    );
    if (!hover || hover.length == 0) return null;
    if (typeof hover[0].contents[0] === 'string')
        return hover[0].contents[0];
    else return hover[0].contents[0].value;
}

/**
 * 获取结构体字段的详细信息
 */
export async function getStructFieldDefinition(
    filePath: string,
    structName: string
): Promise<Array<{ name: string, Definition: string, range: vscode.Range }>> {
    try {
        const uri = getFileUri(filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );

        if (!symbols) return [];

        var structSymbol = findSymbolByName(symbols, structName);
        if (!structSymbol || !structSymbol.children) return [];
        console.log('structSymbol:', structSymbol);
        if (structSymbol.children.length === 0 && structSymbol.kind === vscode.SymbolKind.Interface) {
            structSymbol = findUnnamedStructSymbolByInterfaceName(symbols, structName)
        }
        if (!structSymbol || !structSymbol.children) return [];
        const fieldTypes: Array<{ name: string, Definition: string, range: vscode.Range }> = [];

        for (const field of structSymbol.children) {
            if (field.kind === vscode.SymbolKind.Field) {
                // 获取字段的信息
                const fieldPosition = field.selectionRange.start;
                const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
                    'vscode.executeHoverProvider',
                    document.uri,
                    fieldPosition
                );

                let fieldDefinition = 'unknown';
                if (hovers && hovers.length > 0) {
                    const hoverContent = hovers[0].contents[0];
                    console.log('hoverContent:', hoverContent);
                    if (typeof hoverContent === 'string') {
                        fieldDefinition = hoverContent;
                    } else if ('value' in hoverContent) {
                        fieldDefinition = hoverContent.value;
                    }
                }

                fieldTypes.push({
                    name: field.name,
                    Definition: fieldDefinition,
                    range: field.range
                });
            }
        }

        return fieldTypes;
    } catch (error) {
        console.error('Error getting struct field types:', error);
        return [];
    }
}

/**
 * Gets the document outline of a specified file
 * @param filePath Path to the file to analyze
 * @returns Promise with outline or error
 */
export async function getDocumentOutline(filePath: string): Promise<string | null> {
    try {
        ensureAllCppExtensionsActive()
        checkCppExtensions()
        // Open the document
        const uri = getFileUri(filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        // Get outline using VS Code's built-in functionality
        const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );

        if (!symbols || symbols.length === 0) {
            console.log(`No outline found for file ${filePath}`);
        }
        if (symbols === undefined) {
            console.log('❌ No symbol provider available for this file type');
            return "";
        } else if (symbols === null) {
            console.log('❌ Symbol provider returned null (possible error)');
            return "";
        } else if (!Array.isArray(symbols)) {
            console.log('❌ Unexpected return type:', typeof symbols);
            return "";
        } else if (symbols.length === 0) {
            console.log('⚠️ Symbol provider found no symbols in file');
            return "";
        } else {
            console.log('✅ Found symbols:', symbols.length);
        }

        // Format the symbols into a hierarchical outline
        const outline = formatSymbolsToOutline(symbols);
        return outline;
    } catch (error) {
        console.error('Error getting document outline:', error);
        return null;
    }
}

/**
 * Formats document symbols into a hierarchical outline
 * @param symbols The document symbols to format
 * @param indent The indentation level for nested symbols
 * @returns A formatted string representing the outline
 */
function formatSymbolsToOutline(
    symbols: vscode.DocumentSymbol[],
    indent: string = ''
): string {
    let outline = '';

    for (const symbol of symbols) {
        // Add the symbol to the outline
        outline += `${indent}${symbol.name} (${vscode.SymbolKind[symbol.kind]})\n`;

        // Recursively add child symbols
        if (symbol.children && symbol.children.length > 0) {
            outline += formatSymbolsToOutline(symbol.children, indent + '  ');
        }
    }

    return outline;
}

/**
 * Finds the position of a symbol in a document
 * @param document The document to search in
 * @param symbolName The name of the symbol to find
 * @returns The position of the symbol or undefined if not found
 */
export async function findSymbolPosition(
    document: vscode.TextDocument,
    symbolName: string
): Promise<vscode.Position | undefined> {
    // Get all symbols in the document
    const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
        'vscode.executeDocumentSymbolProvider',
        document.uri
    );

    if (!symbols) {
        return undefined;
    }

    // Search for the symbol with the given name
    const symbol = findSymbolByName(symbols, symbolName);
    if (symbol) {
        return symbol.selectionRange.start;
    }

    return undefined;
}

/**
 * Recursively searches for a structure symbol without name (define with typedef)
 * @param symbols The symbols to search through
 * @param name The Interface name of the symbol to find
 * @returns The found symbol or undefined if not found
 */
function findUnnamedStructSymbolByInterfaceName(
    symbols: vscode.DocumentSymbol[],
    name: string
): vscode.DocumentSymbol | undefined {
    var i = 0;
    for (i = 0; i < symbols.length; i++) {
        var symbol = symbols[i];
        if (symbol.name === name) {
            return symbols[i + 1];
        }

        if (symbol.children && symbol.children.length > 0) {
            const foundInChildren = findSymbolByName(symbol.children, name);
            if (foundInChildren) {
                return foundInChildren;
            }
        }
    }

    return undefined;
}

/**
 * Recursively searches for a symbol by name
 * @param symbols The symbols to search through
 * @param name The name of the symbol to find
 * @returns The found symbol or undefined if not found
 */
function findSymbolByName(
    symbols: vscode.DocumentSymbol[],
    name: string
): vscode.DocumentSymbol | undefined {
    for (const symbol of symbols) {
        if (symbol.name === name) {
            return symbol;
        }

        if (symbol.children && symbol.children.length > 0) {
            const foundInChildren = findSymbolByName(symbol.children, name);
            if (foundInChildren) {
                return foundInChildren;
            }
        }
    }

    return undefined;
}

export interface OutgoingCallReference {
    to: {
        name: string;
        uri: vscode.Uri;
        range: vscode.Range;
    };
    fromRanges: vscode.Range[];
}

export interface IncomingCallReference {
    from: {
        name: string;
        uri: vscode.Uri;
        range: vscode.Range;
    };
    fromRanges: vscode.Range[];
}

// 使用联合类型
export type CallReference = OutgoingCallReference | IncomingCallReference;

/**
 * Gets the outgoing calls from a symbol in a file
 * @param filePath Path to the file containing the symbol
 * @param symbolName Name of the symbol to analyze
 * @returns Promise with outgoing calls or empty array
 */
export async function getOutgoingCalls(
    filePath: string,
    symbolName: string
): Promise<CallReference[]> {
    try {
        // Open the document
        const uri = getFileUri(filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        // Find the symbol's position
        const position = await findSymbolPosition(document, symbolName);
        if (!position) {
            console.log(`Symbol ${symbolName} not found in file ${filePath}`);
            return [];
        }

        // Prepare call hierarchy
        const callHierarchyItems = await vscode.commands.executeCommand<vscode.CallHierarchyItem[]>(
            'vscode.prepareCallHierarchy',
            document.uri,
            position
        );

        if (!callHierarchyItems || callHierarchyItems.length === 0) {
            console.log('No call hierarchy item found!');
            return [];
        }

        // Get outgoing calls
        const outgoingCalls = await vscode.commands.executeCommand<vscode.CallHierarchyOutgoingCall[]>(
            'vscode.provideOutgoingCalls',
            callHierarchyItems[0]
        );

        if (!outgoingCalls || outgoingCalls.length === 0) {
            return [];
        }

        // Format the outgoing calls
        return outgoingCalls.map(call => ({
            to: {
                name: call.to.name,
                uri: call.to.uri,
                range: call.to.range
            },
            fromRanges: call.fromRanges
        }));
    } catch (error) {
        console.error('Error getting outgoing calls:', error);
        return [];
    }
}


/**
 * Get the definition location of a symbol in a file
 */
export async function getSymbolDefinition(
    filePath: string,
    symbolName: string
): Promise<{
    uri: {
        fsPath: string;  // 显式包含 fsPath
    };
    range: vscode.Range;
} | null> {
    const uri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(uri);

    const position = await findSymbolPosition(document, symbolName);
    if (!position) {
        throw new Error(`Symbol ${symbolName} not found in file ${filePath}`);
    }

    const definitions = await vscode.commands.executeCommand<vscode.Location[]>(
        'vscode.executeDefinitionProvider',
        document.uri,
        position
    );

    if (!definitions || definitions.length === 0) {
        return null;
    }

    return {
        uri: {
            fsPath: definitions[0].uri.fsPath  // 显式返回 fsPath
        },
        range: definitions[0].range
    };
}

/**
 * Get all references of a symbol in a file
 */
export async function getSymbolReferences(
    filePath: string,
    symbolName: string
): Promise<Array<{
    uri: {
        fsPath: string;  // 显式包含 fsPath
    };
    range: vscode.Range;
}>> {
    const uri = getFileUri(filePath);
    const document = await vscode.workspace.openTextDocument(uri);

    const position = await findSymbolPosition(document, symbolName);
    if (!position) {
        throw new Error(`Symbol ${symbolName} not found in file ${filePath}`);
    }

    const references = await vscode.commands.executeCommand<vscode.Location[]>(
        'vscode.executeReferenceProvider',
        document.uri,
        position
    );

    if (!references) {
        return [];
    }

    return references.map(ref => ({
        uri: {
            fsPath: ref.uri.fsPath  // 显式返回 fsPath
        },
        range: ref.range
    }));
}


/**
 * Gets the incoming calls to a symbol in a file
 * @param filePath Path to the file containing the symbol
 * @param symbolName Name of the symbol to analyze
 * @returns Promise with incoming calls or empty array
 */
export async function getIncomingCalls(
    filePath: string,
    symbolName: string
): Promise<CallReference[]> {
    try {
        // Open the document
        const uri = getFileUri(filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        // Find the symbol's position
        const position = await findSymbolPosition(document, symbolName);
        if (!position) {
            console.log(`Symbol ${symbolName} not found in file ${filePath}`);
            return [];
        }

        // Prepare call hierarchy
        const callHierarchyItems = await vscode.commands.executeCommand<vscode.CallHierarchyItem[]>(
            'vscode.prepareCallHierarchy',
            document.uri,
            position
        );

        if (!callHierarchyItems || callHierarchyItems.length === 0) {
            console.log('No call hierarchy item found!');
            return [];
        }

        // Get incoming calls
        const incomingCalls = await vscode.commands.executeCommand<vscode.CallHierarchyIncomingCall[]>(
            'vscode.provideIncomingCalls',
            callHierarchyItems[0]
        );

        if (!incomingCalls || incomingCalls.length === 0) {
            return [];
        }

        // Format the incoming calls
        return incomingCalls.map(call => ({
            from: {
                name: call.from.name,
                uri: call.from.uri,
                range: call.from.range
            },
            fromRanges: call.fromRanges
        }));
    } catch (error) {
        console.error('Error getting incoming calls:', error);
        return [];
    }
}

/**
 * Gets the function body from a file path and symbol name
 * @param filePath Path to the file containing the function
 * @param symbolName Name of the function to extract
 * @returns Promise with function body or null if not found
 */
export async function getFunctionBodyFromPath(
    filePath: string,
    symbolName: string
): Promise<{ functionBody: string; range: { start: { line: number; character: number }; end: { line: number; character: number } } } | null> {
    try {
        // Open the document
        const uri = vscode.Uri.file(filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        // Find the symbol
        const symbols = await vscode.commands.executeCommand<vscode.DocumentSymbol[]>(
            'vscode.executeDocumentSymbolProvider',
            document.uri
        );

        if (!symbols) {
            return null;
        }

        // Search for the function symbol
        const functionSymbol = findSymbolByName(symbols, symbolName);
        if (!functionSymbol) {
            return null;
        }

        // Extract the function body and return a serializable range object
        const range = functionSymbol.range;
        const functionBody = document.getText(range);
        const rangeObj = {
            start: { line: range.start.line, character: range.start.character },
            end: { line: range.end.line, character: range.end.character }
        };

        return { functionBody, range: rangeObj };
    } catch (error) {
        console.error('Error getting function body:', error);
        return null;
    }
} 