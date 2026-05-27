import { Request, Response, Router } from 'express';
import { runCustomShellCommand, runEspIdfCommand, runPlatformIOCommand } from '../tools/terminal';

const terminalRouter = Router();

/**
 * API to execute a command in the VSCode terminal.
 * @route POST /api/executeCommandInPioTerminal
 * @bodyParam {string} commandLine - The command line to execute
 * @returns {object} 200 - The output of the command in JSON format.
 * @returns {object} 500 - If an error occurs during command execution.
 */
terminalRouter.post('/executeCommandInPioTerminal', async (req: Request, res: Response) => {
    const commandLine = req.body.commandLine as string;

    try {
        const output = await runPlatformIOCommand(commandLine, 60000 * 5);
        return res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

terminalRouter.post('/executeCommandInEspIdfTerminal', async (req: Request, res: Response) => {
    const commandLine = req.body.commandLine as string;

    try {
        const output = await runEspIdfCommand(commandLine, 60000 * 5);
        return res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

terminalRouter.post('/executeCommandInTerminal', async (req: Request, res: Response) => {
    const commandLine = req.body.commandLine as string;

    try {
        const output = await runCustomShellCommand(commandLine, 60000 * 5);
        return res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

export default terminalRouter;