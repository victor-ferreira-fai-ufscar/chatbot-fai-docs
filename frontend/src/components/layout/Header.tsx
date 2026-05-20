import Image from 'next/image';
import { Menu, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar: () => void;
  isBackendConnected: boolean | null;
}

export default function Header({ onToggleSidebar, isBackendConnected }: HeaderProps) {
  return (
    <header className="h-14 bg-header-blue flex items-center px-4 shadow-md z-10 transition-all duration-300 justify-between">
      <div className="flex items-center gap-4">
        {/* Toggle Button */}
        <button 
          onClick={onToggleSidebar}
          className="text-white hover:bg-white/10 p-1 rounded-md transition-colors"
          title="Alternar Menu"
        >
          <Menu size={24} />
        </button>

        <div className="flex items-center gap-3">
          <Image 
            src="/logo-fai.png" 
            alt="FAI-Ufscar Logo" 
            width={32} 
            height={32} 
            className="object-contain"
          />
          <h1 className="text-white text-xl font-bold tracking-tight hidden sm:block" style={{ fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif' }}>
            Fai-Ufscar
          </h1>
        </div>
      </div>

      {/* Backend Connection Status */}
      <div className="flex items-center gap-2 mr-2">
        {isBackendConnected === true && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-green-500/20 text-green-100 rounded-full text-xs font-medium border border-green-500/30" title="API Conectada">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            <span className="hidden sm:inline">Online</span>
          </div>
        )}
        {isBackendConnected === false && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-red-500/20 text-red-100 rounded-full text-xs font-medium border border-red-500/30" title="API Desconectada">
            <WifiOff size={12} className="text-red-400" />
            <span className="hidden sm:inline">Offline</span>
          </div>
        )}
      </div>
    </header>
  );
}
