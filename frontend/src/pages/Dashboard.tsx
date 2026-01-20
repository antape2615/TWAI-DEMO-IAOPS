import { useEffect, useState } from 'react';
import { BarChart3, Cloud, Users, Sparkles, TrendingUp, Activity } from 'lucide-react';
import { clientService } from '@/services/clientService';
import { Client } from '@/types';

export function Dashboard() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    try {
      const data = await clientService.getAll();
      setClients(data);
    } catch (error) {
      console.error('Error loading clients:', error);
    } finally {
      setLoading(false);
    }
  };

  const stats = [
    {
      name: 'Total Clientes',
      value: clients.length,
      icon: Users,
      color: 'text-blue-600',
      bg: 'bg-blue-100',
    },
    {
      name: 'Arquitecturas Generadas',
      value: '24',
      icon: Sparkles,
      color: 'text-purple-600',
      bg: 'bg-purple-100',
    },
    {
      name: 'Despliegues Activos',
      value: '12',
      icon: Cloud,
      color: 'text-green-600',
      bg: 'bg-green-100',
    },
    {
      name: 'Recursos Cloud',
      value: '156',
      icon: BarChart3,
      color: 'text-orange-600',
      bg: 'bg-orange-100',
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Bienvenido a la plataforma IAOPS - Intelligent AI Operations
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.name} className="card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">{stat.name}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">
                    {stat.value}
                  </p>
                </div>
                <div className={`p-3 rounded-lg ${stat.bg}`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Activity Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Actividad Reciente
            </h2>
            <Activity className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-4">
            {[
              {
                action: 'Arquitectura generada',
                client: 'Empresa ABC',
                time: 'Hace 2 horas',
              },
              {
                action: 'Despliegue completado',
                client: 'Tech Corp',
                time: 'Hace 4 horas',
              },
              {
                action: 'Cliente creado',
                client: 'Startup XYZ',
                time: 'Hace 1 día',
              },
            ].map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0"
              >
                <div>
                  <p className="font-medium text-gray-900">{activity.action}</p>
                  <p className="text-sm text-gray-500">{activity.client}</p>
                </div>
                <span className="text-xs text-gray-400">{activity.time}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Clouds en Uso
            </h2>
            <Cloud className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-4">
            {[
              { name: 'AWS', clients: 8, color: 'bg-orange-500' },
              { name: 'Azure', clients: 5, color: 'bg-blue-500' },
              { name: 'GCP', clients: 3, color: 'bg-green-500' },
            ].map((cloud) => (
              <div key={cloud.name}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {cloud.name}
                  </span>
                  <span className="text-sm text-gray-500">
                    {cloud.clients} clientes
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${cloud.color}`}
                    style={{ width: `${(cloud.clients / 16) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Acciones Rápidas
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="btn btn-primary flex items-center justify-center space-x-2">
            <Users className="w-5 h-5" />
            <span>Nuevo Cliente</span>
          </button>
          <button className="btn btn-primary flex items-center justify-center space-x-2">
            <Sparkles className="w-5 h-5" />
            <span>Generar Arquitectura</span>
          </button>
          <button className="btn btn-primary flex items-center justify-center space-x-2">
            <Cloud className="w-5 h-5" />
            <span>Ver Recursos</span>
          </button>
        </div>
      </div>
    </div>
  );
}
