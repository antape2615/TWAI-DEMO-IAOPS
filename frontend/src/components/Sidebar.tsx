import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  Users,
  Boxes,
  Sparkles,
  Settings,
  BarChart3,
  Activity
} from 'lucide-react';
import { clsx } from 'clsx';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Clientes', href: '/clients', icon: Users },
  { name: 'Arquitecturas', href: '/architectures', icon: Boxes },
  { name: 'Monitoreo', href: '/monitoring', icon: Activity },
  { name: 'Generador IA', href: '/ai-generator', icon: Sparkles },
  { name: 'Despliegues', href: '/deployments', icon: BarChart3 },
  { name: 'Configuración', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const location = useLocation();

  return (
    <div className="flex flex-col w-64 bg-gray-900 min-h-screen">
      <div className="flex items-center justify-center h-16 px-4 bg-gray-800">
        <h1 className="text-2xl font-bold text-white">
          <span className="text-primary-400">IA</span>OPS
        </h1>
      </div>

      <nav className="flex-1 px-4 py-6 space-y-2">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              to={item.href}
              className={clsx(
                'flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )}
            >
              <Icon className="w-5 h-5 mr-3" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-4 bg-gray-800">
        <p className="text-xs text-gray-400 text-center">
          IAOPS Platform v1.0.0
        </p>
      </div>
    </div>
  );
}
