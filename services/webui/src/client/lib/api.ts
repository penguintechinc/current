import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

const getStoredToken = () => {
    try {
        const storage = localStorage.getItem('auth-storage');
        if (storage) {
            const parsed = JSON.parse(storage);
            return parsed.state?.accessToken;
        }
    } catch (e) {
        return null;
    }
    return null;
};

let currentAccessToken: string | null = null;

export const setTokens = (access: string, ref: string) => {
    currentAccessToken = access;
};

export const clearTokens = () => {
    currentAccessToken = null;
};

export const getAccessToken = () => {
    return currentAccessToken || getStoredToken();
};

api.interceptors.request.use(
    (config) => {
        const token = getAccessToken();
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

export default api;
