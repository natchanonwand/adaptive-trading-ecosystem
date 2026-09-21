import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { mockClient, realClient } from './client';
import './styles.css';

const mock = new URLSearchParams(window.location.search).get('mock') === '1';
const root = document.getElementById('root');
if (!root) throw new Error('Dashboard root missing');
createRoot(root).render(
  <StrictMode>
    <App client={mock ? mockClient : realClient} />
  </StrictMode>,
);
