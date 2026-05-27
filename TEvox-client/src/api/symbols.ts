import { Request, Response, Router } from 'express';
import {
    getDocumentOutline,
    getOutgoingCalls,
    getIncomingCalls,
    getSymbolReferences,
    getSymbolDefinition,
    getFunctionBodyFromPath,
    getStructFieldDefinition,
    getSymbolHover,
    getClassMembers,
    findSymbolsReferThisSymbol
} from '../tools/symbols';

const symbolsRouter = Router();

symbolsRouter.get('/find_symbols_refer_this_symbol', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;
    const start_line = parseInt(req.query.start_line as string, 10);
    const end_line = parseInt(req.query.end_line as string, 10);

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: "File path and symbol name are required" });
    }
    try {
        const symbol = await findSymbolsReferThisSymbol(filePath, symbolName, start_line, end_line);
        return res.status(200).json({ symbol });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to find symbol' });
    }

});

symbolsRouter.get('/class_members', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const className = req.query.className as string;

    if (!filePath || !className) {
        return res.status(400).json({ error: 'File path and class name are required' });
    }

    try {
        const members = await getClassMembers(filePath, className);
        return res.status(200).json({ members });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get class members' });
    }
});

symbolsRouter.get('/symbol_hover', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'File path and symbol name are required' });
    }

    try {
        const hover = await getSymbolHover(filePath, symbolName);
        return res.status(200).json({ hover });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get symbol hover' });
    }
})


/**
 * API to get field definition of a struct
 * @route GET /struct_fields
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} structName - The struct name to analyze
 */
symbolsRouter.get('/struct_fields', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const structName = req.query.structName as string;

    if (!filePath || !structName) {
        return res.status(400).json({ error: 'File path and struct name are required' });
    }

    try {
        const fields = await getStructFieldDefinition(filePath, structName);
        return res.status(200).json({ fields });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get struct field types' });
    }
});



/**
 * API to get symbol definition in a file
 * @route GET /definition
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to find definition for
 */
symbolsRouter.get('/definition', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'File path and symbol name are required' });
    }

    try {
        const definition = await getSymbolDefinition(filePath, symbolName);
        return res.status(200).json({ definition });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get symbol definition' });
    }
});

/**
 * API to get all references of a symbol in a file
 * @route GET /references
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to find references for
 */
symbolsRouter.get('/references', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'File path and symbol name are required' });
    }

    try {
        const references = await getSymbolReferences(filePath, symbolName);
        return res.status(200).json({ references });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get symbol references' });
    }
});



/**
 * API to get document outline for a file
 * @route GET /outline
 * @queryParam {string} filePath - The file path to analyze
 */
symbolsRouter.get('/outline', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;

    if (!filePath) {
        return res.status(400).json({ error: 'File path is required' });
    }

    try {
        const outline = await getDocumentOutline(filePath);
        if (outline === "") {
            return res.status(404).json({ error: 'No outline found' });
        } else if (outline === null) {
            return res.status(404).json({ error: 'Failed to get document outline' });
        } else {
            return res.status(200).json({ outline });
        }
    } catch (error) {
        console.error(error);
        return res.status(500).json({ error: 'Failed to get document outline' });
    }
});

/**
 * API to get outgoing calls for a symbol in a file
 * @route GET /outgoing_calls
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to find calls for
 */
symbolsRouter.get('/outgoing_calls', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'File path and symbol name are required' });
    }

    try {
        const outgoingCalls = await getOutgoingCalls(filePath, symbolName);
        return res.status(200).json({ outgoingCalls });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get outgoing calls' });
    }
});

/**
 * API to get incoming calls for a symbol in a file
 * @route GET /incoming_calls
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to find calls for
 */
symbolsRouter.get('/incoming_calls', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'File path and symbol name are required' });
    }

    try {
        const incomingCalls = await getIncomingCalls(filePath, symbolName);
        return res.status(200).json({ incomingCalls });
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get incoming calls' });
    }
});

/**
 * API to get functions called by a symbol in a file
 * @route GET /function_calls
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to find calls for
 */
symbolsRouter.get('/function_calls', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'Missing filePath or symbolName parameter' });
    }

    try {
        const result = await getOutgoingCalls(filePath, symbolName);
        return res.status(200).json(result);
    } catch (error) {
        console.error('Error processing request:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

/**
 * API to get function body for a symbol in a file
 * @route GET /function_body
 * @queryParam {string} filePath - The file path to analyze
 * @queryParam {string} symbolName - The symbol name to get body for
 */
symbolsRouter.get('/function_body', async (req: Request, res: Response) => {
    const filePath = req.query.filePath as string;
    const symbolName = req.query.symbolName as string;

    if (!filePath || !symbolName) {
        return res.status(400).json({ error: 'filePath and symbolName are required' });
    }

    try {
        const result = await getFunctionBodyFromPath(filePath, symbolName);
        if (result) {
            // result contains { functionBody, range }
            return res.status(200).json(result);
        } else {
            return res.status(404).json({ error: `symbolName ${symbolName} not found` });
        }
    } catch (error) {
        return res.status(500).json({ error: 'Failed to get function body' });
    }
});

export default symbolsRouter; 