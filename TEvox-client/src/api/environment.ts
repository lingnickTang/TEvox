import { Request, Response, Router } from 'express';
import { 
    initializeEnvironment,
    getPythonEnvironment
} from '../tools/environment';

const environmentRouter = Router();

/**
 * API to initialize all paths and Python environment
 * @route POST /initialize
 * @bodyParam {string} extensionPath - Path to the extension directory
 */
environmentRouter.post('/initialize', async (req: Request, res: Response) => {
    try {
        const { extensionPath } = req.body;
        
        if (!extensionPath) {
            return res.status(400).json({ error: 'Extension path is required' });
        }
        
        await initializeEnvironment(extensionPath);
        return res.status(200).json({ message: 'Environment initialized successfully' });
    } catch (error) {
        console.error('Error initializing environment:', error);
        return res.status(500).json({ error: 'Failed to initialize environment' });
    }
});

/**
 * API to get current Python environment settings
 * @route GET /python
 */
environmentRouter.get('/python', (req: Request, res: Response) => {
    try {
        const environment = getPythonEnvironment();
        return res.status(200).json(environment);
    } catch (error) {
        console.error('Error getting Python environment:', error);
        return res.status(500).json({ error: 'Failed to get Python environment' });
    }
});

export default environmentRouter; 