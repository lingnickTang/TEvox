import { Request, Response, Router } from 'express';
import { findReferences } from '../tools/navigation';

const navigationRouter = Router();

/**
 * API to find references to the selected symbol in the given file at the specified line number.
 * @route GET /find_references
 * @queryParam {string} filePath - The file path (absolute or relative to the workspace).
 * @queryParam {number} lineNumber - The line number to find references.
 * @queryParam {string} selectedSymbol - The symbol to find references.
 * @returns {object} 200 - The references to the selected symbol.
 * @returns {object} 500 - If an error occurs during reference finding.
 */
navigationRouter.get('/find_references', async (req: Request, res: Response) => {
    const filePath = req.body.filePath as string;
    const lineNumber = req.body.lineNumber as number - 1;
    const selectedSymbol = req.body.selectedSymbol as string;

    try {
        const references = await findReferences(filePath, lineNumber, selectedSymbol);
        res.status(200).send(JSON.stringify(references));
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        res.status(500).send(errorMessage);
    }
});

export default navigationRouter;

