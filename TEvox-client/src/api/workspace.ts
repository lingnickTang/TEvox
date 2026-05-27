import { Request, Response, Router } from 'express';
import * as vscode from 'vscode';
import { closeAllOpenTextDocuments, closeFile, deleteFileOrDirectory, getAllOpenTextDocumentsString, getDirectoryFiles, openFile, readFile, renamePath, writeFile } from '../tools/workspace';

const workspaceRouter = Router();

/**
 * API to open a file in the editor.
 * @route POST /openFile
 * @bodyParam {string} filePath - The path to the file to open.
 * @returns {object} 200 - A success message when the file is opened successfully.
 * @returns {object} 500 - If an error occurs during file opening.
 */
workspaceRouter.post('/openFile', async (req: Request, res: Response) => {
    const filePath = req.body.filePath as string;
    try {
        const document = await openFile(filePath);
        const currText = await readFile(document, true);
        res.send(currText);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error opening file at path ${filePath}: ${errorMessage}`);
    }
});


/**
 * API to close a file in the editor.
 * @route POST /closeFile
 * @bodyParam {string} filePath - The path to the file to close.
 * @returns {object} 200 - A success message when the file is closed successfully.
 * @returns {object} 500 - If an error occurs during file closing.
 */
workspaceRouter.post('/closeFile', async (req: Request, res: Response) => {
    const filePath = req.body.filePath as string;

    try {
        await closeFile(filePath);
        res.send(`File closed successfully at path ${filePath}.`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error closing file at path ${filePath}: ${errorMessage}`);
    }
});


/**
 * API to write the content of a file.
 * @route POST /writeFile
 * @bodyParam {string} filePath - The path to the file to be written.
 * @bodyParam {string} newText - The new content to write into the file.
 * @bodyParam {number} startLine - The line number to start writing the content.
 * @bodyParam {number} endLine - The line number to end writing the content.
 * @returns {object} 200 - A success message when the file is written successfully.
 * @returns {object} 500 - If an error occurs during file writing.
 */
workspaceRouter.post('/writeFile', async (req: Request, res: Response) => {
    const filePath = req.body.filePath as string;
    const newText = req.body.newText as string;
    const startLine = req.body.startLine as number;
    const endLine = req.body.endLine as number;
    const editType = req.body.editType as string;

    try {
        const diff = await writeFile(filePath, startLine, endLine, newText, editType);
        diff.msg = `File written successfully at path ${diff.filePath} from line ${startLine} to line ${endLine}. Original file content: ${diff.oldText}. Current file content: ${diff.newText}`
        // res.status(200).send(JSON.stringify(diff));
        res.status(200).send(`File written successfully.`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error writing file at path ${filePath} from line ${startLine} to line ${endLine}: ${errorMessage}`);
    }
});


/**
 * API to delete a file or directory.
 * @route DELETE /deleteFileOrDirectory
 * @queryParam {string} path - The path to the file or directory to delete. Must be an absolute or workspace-relative path.
 * @returns {object} 200 - A success message when the file or directory is deleted successfully.
 * @returns {object} 500 - If an error occurs during deletion.
 */
workspaceRouter.delete('/deleteFileOrDirectory', async (req: Request, res: Response) => {
    const path = req.query.path as string;

    try {
        await deleteFileOrDirectory(path);
        res.send(`Path ${path} deleted successfully.`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error deleting path ${path}: ${errorMessage}`);
    }
});


/**
 * API to get the files in a directory, optionally recursively.
 * @route GET / getDirectoryFiles
 * @queryParam { string } path - The path to the directory.Must be absolute or workspace - relative.
 * @queryParam { boolean } [recursive = false] - Whether to recursively read subdirectories.
 * @returns { object } 200 - Files in JSON format(flat list with `depth` field).
 * @returns { object } 500 - Error message if reading fails.
 */
workspaceRouter.get('/getDirectoryFiles', async (req: Request, res: Response) => {
    const path = req.query.path as string;
    const recursive = req.query.recursive === 'true';

    try {
        const files = await getDirectoryFiles(path, recursive);
        res.send(files);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error reading directory at ${path}: ${errorMessage}`);
    }
});

/**
 * API to get all open text documents in the editor.
 * @route GET /getAllOpenTextDocuments
 * @returns {object} 200 - The list of open text documents in JSON format.
 * @returns {object} 500 - If an error occurs during fetching the open text documents.
 */
workspaceRouter.get('/getAllOpenTextDocuments', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;

    try {
        const content = await getAllOpenTextDocumentsString();
        res.status(200).send(content);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error fetching open text documents: ${errorMessage}`);
    }
});

/**​
 * API to close all open text documents in the editor.
 * @route POST /closeAllOpenTextDocuments
 * @returns {object} 200 - Success message when all documents are closed.
 * @returns {object} 500 - If an error occurs during closing the documents.
 */
workspaceRouter.post('/closeAllOpenTextDocuments', async (req: Request, res: Response) => {
    try {
        await closeAllOpenTextDocuments();
        res.status(200).send("All open text documents have been closed successfully.");
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error closing open text documents: ${errorMessage}`);
    }
});

workspaceRouter.post('/findInFilesOfWorkspace', async (req: Request, res: Response) => {
    const {
        query,
        replace,
        triggerSearch,
        filesToInclude,
        filesToExclude,
        isRegex,
        isCaseSensitive,
        matchWholeWord,
    } = req.body;

    try {
        await vscode.commands.executeCommand('workbench.action.findInFiles',
            {
                "query": query,
                "replace": replace,
                "triggerSearch": triggerSearch,
                "filesToInclude": filesToInclude,
                "filesToExclude": filesToExclude,
                "isRegex": isRegex,
                "isCaseSensitive": isCaseSensitive,
                "matchWholeWord": matchWholeWord,

            }
        );
        await new Promise((resolve) => setTimeout(resolve, 10000));
        await vscode.commands.executeCommand('search.action.openInEditor');
        await new Promise((resolve) => setTimeout(resolve, 10000));
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            console.log(activeEditor.document.fileName);
            const content = activeEditor.document.getText();
            // await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
            res.status(200).send(content);
        } else {
            res.status(400).send('Error performing find in files: No active editor found.');
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error performing find in files: ${errorMessage}`);
    }
});

workspaceRouter.post('/renamePath', async (req: Request, res: Response) => {
    const { oldPath, newPath } = req.body;
    try {
        await renamePath(oldPath, newPath);
        res.status(200).send(`Renamed ${oldPath} to ${newPath} successfully.`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(`Error renaming ${oldPath} to ${newPath}: ${errorMessage}`);
    }
});

export default workspaceRouter;