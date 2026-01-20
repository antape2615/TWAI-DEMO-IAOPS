import { Loader2 } from 'lucide-react';

interface LoadingProps {
  text?: string;
}

export function Loading({ text = 'Cargando...' }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center h-64">
      <Loader2 className="w-12 h-12 text-primary-600 animate-spin" />
      <p className="mt-4 text-gray-600">{text}</p>
    </div>
  );
}
