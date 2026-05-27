declare global {
    interface Window {
        acquireVsCodeApi(): {
            postMessage(message: any): void;
            getState(): any;
            setState(state: any): void;
        };
    }
}

export {};
