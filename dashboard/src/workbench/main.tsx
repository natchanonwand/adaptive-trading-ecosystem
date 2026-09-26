import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Workbench } from './Workbench';
import '../styles.css';
import './workbench.css';

const root = document.getElementById('root');
if (!root) throw new Error('Workbench root missing');
createRoot(root).render(
  <StrictMode>
    <Workbench />
  </StrictMode>,
);
