import { StackFrame } from "@vscode/debugadapter";
import * as vscode from 'vscode';
import { runPlatformIOCommand } from './terminal';

interface SimpleBreakpoint {
    path: string;
    line: number;
}

interface SimpleStackFrame {
    name: string;
    line: number;
    source: string;
}

export interface PausedState {
    breakpoints: SimpleBreakpoint[];
    pausedStack: SimpleStackFrame[];
    topFrameVariables: {
        scopeName: string;
        variables: Record<string, any>[];
    }[];
}

export async function startDebugging() {
    await runPlatformIOCommand('pio -h', 3000);

    if (vscode.debug.activeDebugSession) {
        await vscode.commands.executeCommand('workbench.action.debug.stop');
    }

    const configuration = vscode.workspace.getConfiguration('launch');
    const configurations = configuration.get<any[]>('configurations');

    if (!configurations || configurations.length === 0) {
        throw new Error('No launch configuration found in launch.json');
    }

    await vscode.debug.startDebugging(vscode.workspace.workspaceFolders![0], configurations[0].name);
}

export async function executeDebugAction(action: string) {
    if (!vscode.debug.activeDebugSession) {
        throw new Error('No active debug session. Please start a debug session first.');
    }
    await vscode.commands.executeCommand(`workbench.action.debug.${action}`);
}

export function getEnabledBreakpoints(): SimpleBreakpoint[] {
    const breakpoints = new Array<SimpleBreakpoint>();

    for (const breakpoint of vscode.debug.breakpoints) {
        if (breakpoint instanceof vscode.SourceBreakpoint && breakpoint.enabled) {
            breakpoints.push({
                path: breakpoint.location.uri.fsPath,
                line: breakpoint.location.range.start.line + 1,
            });

        }
    }

    return breakpoints;
}

export async function getStackFrames(session: vscode.DebugSession): Promise<StackFrame[]> {
    const threadsResponse = await session.customRequest("threads");
    const allThreads = threadsResponse?.threads || [];

    const pausedThread = allThreads[0];
    if (!pausedThread) {
        return [];
    }

    const stackTraceResponse = await session.customRequest("stackTrace", {
        threadId: pausedThread.id,
        startFrame: 0,
        levels: 20,
    });

    return stackTraceResponse.stackFrames || [];;
}

export async function getPausedStack(session: vscode.DebugSession): Promise<SimpleStackFrame[]> {
    const stackFrames = await getStackFrames(session);
    return stackFrames.map((frame: StackFrame) => ({
        name: frame.name,
        line: frame.line,
        source: frame.source!.path || frame.source!.name || '<unknown>',
    }));
}

export async function getReferenceVariables(variables: any[]): Promise<Record<string, any>[]> {
    let result = [];

    for (const variable of variables) {
        if (!variable.variablesReference) {
            result.push({
                name: variable.name,
                value: variable.value,
            });
        } else {
            const nestedVariables = await vscode.debug.activeDebugSession!.customRequest('variables', {
                variablesReference: variable.variablesReference
            });

            const nestedResults = await getReferenceVariables(nestedVariables.variables);

            result.push({
                name: variable.name,
                value: variable.value,
                referenceVariables: nestedResults
            });
        }
    }

    return result;
}

export async function getTopFrameVariables(session: vscode.DebugSession): Promise<{
    scopeName: string;
    variables: Record<string, any>[];
}[]> {
    const stackFrames = await getStackFrames(session);
    if (stackFrames.length === 0) {
        return [];
    }

    const topFrame = stackFrames[0];
    const scopesResponse = await session.customRequest("scopes", {
        frameId: topFrame.id,
    });
    const scopes = scopesResponse.scopes || [];

    const results: {
        scopeName: string;
        variables: Record<string, any>[];
    }[] = [];

    for (const scope of scopes) {
        const variablesResponse = await session.customRequest("variables", {
            variablesReference: scope.variablesReference,
        });

        // results.push({
        //     scopeName: scope.name,
        //     variables: await getReferenceVariables(variablesResponse.variables),
        // });

        results.push({
            scopeName: scope.name,
            variables: variablesResponse.variables.map((variable: any) => ({
                name: variable.name,
                value: variable.value,
            })),
        });
    }

    return results;
}

export async function getPausedState(): Promise<PausedState> {
    const session = vscode.debug.activeDebugSession;
    if (!session) {
        throw new Error('No active debug session. Please start a debug session first.');
    }

    const breakpoints = getEnabledBreakpoints();
    const pausedStack = await getPausedStack(session);
    const topFrameVariables = await getTopFrameVariables(session);

    return {
        breakpoints,
        pausedStack,
        topFrameVariables,
    };
}