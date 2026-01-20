import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Clients } from './pages/Clients';
import { AIGenerator } from './pages/AIGenerator';
import { Resources } from './pages/Resources';

function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/ai-generator" element={<AIGenerator />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/architectures" element={<div>Arquitecturas</div>} />
          <Route path="/deployments" element={<div>Despliegues</div>} />
          <Route path="/settings" element={<div>Configuración</div>} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
