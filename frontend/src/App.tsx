import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Clients } from './pages/Clients';
import { AIGenerator } from './pages/AIGenerator';
import { Monitoring } from './pages/Monitoring';
import { Architectures } from './pages/Architectures';
import { Deployments } from './pages/Deployments';
import { Settings } from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/ai-generator" element={<AIGenerator />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/architectures" element={<Architectures />} />
          <Route path="/deployments" element={<Deployments />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
