import { Request, Response, Router } from 'express';
import * as vscode from 'vscode';
import { executeDebugAction, getPausedState, startDebugging } from '../tools/debugger';

const debugRouter = Router();

/**
 * API to start a debug session in the VSCode debugger.
 * @route POST /start_debugging
 * @returns {object} 200 - A success message when the debug session is started.
 * @returns {object} 500 - If an error occurs during debug session start.
 */
debugRouter.post('/start_debugging', async (req: Request, res: Response) => {
    try {
        await startDebugging();
        res.status(200).send(`debug session started`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`debug session failed, error: ${errorMessage}`);
    }
});

/**
 * API to execute a debug action in the VSCode debugger.
 * @route POST /execute_debug_action
 * @bodyParam {string} action - The debug action to execute.
 * @returns {object} 200 - A success message when the debug action is executed.
 * @returns {object} 500 - If an error occurs during debug action execution.
 */
debugRouter.post('/execute_debug_action', async (req: Request, res: Response) => {
    // 支持的action见: https://github.com/microsoft/vscode-docs/blob/main/docs/editor/debugging.md#debug-actions
    const action = req.body.action as string;

    try {
        await executeDebugAction(action);
        res.status(200).send(`execute debug action: ${action} success`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`execute debug action: ${action} failed, error: ${errorMessage}`);
    }
});

/**
 * API to add a breakpoint in the VSCode debugger.
 * @route POST /add_breakpoint
 * @bodyParam {string} file_path - The path to the file to add a breakpoint.
 * @bodyParam {number} line_number - The line number to add a breakpoint.
 * @returns {object} 200 - A success message when the breakpoint is added.
 * @returns {object} 500 - If an error occurs during breakpoint addition.
 */
debugRouter.post('/add_breakpoint', async (req: Request, res: Response) => {
    const filePath = req.body.file_path;
    const lineNumber = req.body.line_number;

    try {
        let file: vscode.Uri;
        if (filePath.indexOf(":") === -1) {
            const workspaceUri = vscode.workspace.workspaceFolders![0].uri;
            file = vscode.Uri.joinPath(workspaceUri, filePath);
        } else {
            file = vscode.Uri.file(filePath);
        }

        const breakpoint = new vscode.SourceBreakpoint(
            new vscode.Location(file, new vscode.Position(lineNumber - 1, 0))
        );
        vscode.debug.addBreakpoints([breakpoint]);
        res.status(200).send(`add breakpoint success, file ${filePath}, line: ${lineNumber}`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`add breakpoint failed, error: ${errorMessage}`);
    }
});

/**
 * API to remove a breakpoint in the VSCode debugger.
 * @route POST /remove_breakpoint
 * @bodyParam {string} file_path - The path to the file to remove a breakpoint.
 * @bodyParam {number} line_number - The line number to remove a breakpoint.
 * @returns {object} 200 - A success message when the breakpoint is removed.
 * @returns {object} 500 - If an error occurs during breakpoint removal.
 */
debugRouter.post('/remove_breakpoint', async (req: Request, res: Response) => {
    const filePath = req.body.file_path;
    const lineNumber = req.body.line_number;

    try {
        let file: vscode.Uri;
        if (filePath.indexOf(":") === -1) {
            const workspaceUri = vscode.workspace.workspaceFolders![0].uri;
            file = vscode.Uri.joinPath(workspaceUri, filePath);
        } else {
            file = vscode.Uri.file(filePath);
        }

        const breakpoints = vscode.debug.breakpoints.filter(breakpoint =>
            breakpoint instanceof vscode.SourceBreakpoint &&
            breakpoint.location.uri.toString() === file.toString() &&
            breakpoint.location.range.start.line === lineNumber - 1
        );
        vscode.debug.removeBreakpoints(breakpoints);
        res.status(200).send(`remove breakpoint success, file ${filePath}, line: ${lineNumber}`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`remove breakpoint failed, error: ${errorMessage}`);
    }
});

/**
 * API to get the paused state of the current debug session.
 * @route POST /get_paused_state
 * @returns {object} 200 - The paused state of the current debug session.
 * @returns {object} 500 - If an error occurs during paused state retrieval.
 * @returns {object} 400 - If there is no active debug session.
 * @returns {object} 500 - If an error occurs during paused state retrieval.
 */
debugRouter.post('/get_paused_state', async (req: Request, res: Response) => {
    try {
        const pausedState = await getPausedState();
        res.status(200).send(JSON.stringify(pausedState));
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`get paused state failed, error: ${errorMessage}`);
    }
});

export default debugRouter;