import axios from 'axios';

// Base API URL
// In production, this would be an environment variable
export const API_BASE_URL = 'http://localhost:8000/api';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only log non-connection errors to avoid console spam
    if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      // Backend is not running - this is expected if backend hasn't started yet
      console.warn('Backend not available. Please start the backend server on port 8000.');
    } else {
      console.error('API Error:', error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

export default client;

