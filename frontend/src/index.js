import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { ThemeProvider } from './ThemeContext';
import axios from 'axios';

// Configure axios base URL for API calls
// In Docker, frontend needs to call backend through the host's localhost
// In development, proxy in package.json handles this
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
