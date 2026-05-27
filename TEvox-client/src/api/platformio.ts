import { Request, Response, Router } from 'express';
import { runPlatformIOCommand } from '../tools/terminal';

const pioRouter = Router();

/**
 * API to build a device using the PlatformIO extension.
 * @route POST /api/pio/buildDevice
 * @returns {object} 200 - A success message when the device is built successfully.
 * @returns {object} 500 - If an error occurs during device building.
 */
pioRouter.post('/buildDevice', async (req: Request, res: Response) => {
    try {
        const output = await runPlatformIOCommand('pio run', 60000 * 3);
        res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

pioRouter.post('/uploadMonitorDevice', async (req: Request, res: Response) => {
    try {
        const output = await runPlatformIOCommand('pio run --target upload --target monitor', 60000 * 3);
        res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

pioRouter.post('/runTestCases', async (req: Request, res: Response) => {
    try {
        const output = await runPlatformIOCommand('pio test -vvv', 60000 * 5);
        res.status(200).send(output);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

export default pioRouter;

