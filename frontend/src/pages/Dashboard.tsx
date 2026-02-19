import { useEffect, useState } from 'react';
import { BarChart3, Cloud, Users, Sparkles, Activity } from 'lucide-react';
import { dashboardService, DashboardStats } from '@/services/dashboardService';
import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const data = await dashboardService.getStats();
      setStats(data);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      name: 'Total Clientes',
      value: stats?.total_clients || 0,
      icon: Users,
      color: 'text-blue-600',
      bg: 'bg-blue-100',
    },
    {
      name: 'Arquitecturas Generadas',
      value: stats?.total_architectures || 0,
      icon: Sparkles,
      color: 'text-purple-600',
      bg: 'bg-purple-100',
    },
    {
      name: 'Despliegues Exitosos',
      value: stats?.total_deployments || 0,
      icon: Cloud,
      color: 'text-green-600',
      bg: 'bg-green-100',
    },
    {
      name: 'Nubes en Uso',
      value: Object.keys(stats?.cloud_usage || {}).length,
      icon: BarChart3,
      color: 'text-orange-600',
      bg: 'bg-orange-100',
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

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
        {statCards.map((stat) => {
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
            {stats?.recent_activity.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No hay actividad reciente</p>
            ) : (
              stats?.recent_activity.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0"
                >
                  <div>
                    <p className="font-medium text-gray-900">{activity.action}</p>
                    <p className="text-sm text-gray-500">{activity.client}</p>
                  </div>
                  <span className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(activity.time), { addSuffix: true, locale: es })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Uso de Clouds
            </h2>
            <Cloud className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-4">
            {Object.entries(stats?.cloud_usage || {}).length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">Sin datos de nube</p>
            ) : (
              Object.entries(stats?.cloud_usage || {}).map(([name, count]) => {
                const colors: Record<string, string> = {
                  'aws': 'bg-orange-500',
                  'azure': 'bg-blue-500',
                  'gcp': 'bg-green-500'
                };
                return (
                  <div key={name}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700 capitalize">
                        {name}
                      </span>
                      <span className="text-sm text-gray-500">
                        {count} despliegues
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${colors[name.toLowerCase()] || 'bg-gray-500'}`}
                        style={{ width: `${Math.min(100, (count / (stats?.total_deployments || 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Acciones Rápidas
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/clients" className="btn btn-primary flex items-center justify-center space-x-2">
            <Users className="w-5 h-5" />
            <span>Gestionar Clientes</span>
          </a>
          <a href="/generator" className="btn btn-primary flex items-center justify-center space-x-2">
            <Sparkles className="w-5 h-5" />
            <span>Generar Arquitectura</span>
          </a>
          <a href="/resources" className="btn btn-primary flex items-center justify-center space-x-2">
            <Cloud className="w-5 h-5" />
            <span>Ver Recursos</span>
          </a>
        </div>
      </div>
    </div>
  );
}
