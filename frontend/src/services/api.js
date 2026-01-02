const API_URL = 'http://127.0.0.1:8000';

export const checkHealth = async () => {
    try {
        const response = await fetch(`${API_URL}/health`);
        return await response.json();
    } catch (error) {
        console.error('Backend health check failed:', error);
        return { status: 'error', error: error.message };
    }
};

export const sendMessage = async (text) => {
    // Placeholder for LLM interaction
    // const response = await fetch(`${API_URL}/chat`, { ... });
    return { response: "Echo: " + text };
}

export const captureScreen = async () => {
    try {
        const response = await fetch(`${API_URL}/capture`);
        return await response.json();
    } catch (error) {
        console.error('Capture failed:', error);
        return { status: 'error', error: error.message };
    }
};
