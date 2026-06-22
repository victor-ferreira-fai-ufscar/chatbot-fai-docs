import Image from 'next/image';
import { Menu, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';

interface HeaderProps {
  onToggleSidebar: () => void;
  isBackendConnected: boolean | null;
}

export default function Header({ onToggleSidebar, isBackendConnected }: HeaderProps) {
  return (
    <header className="h-14 bg-header-blue flex items-center px-4 shadow-md z-10 transition-all duration-300 justify-between">
      <div className="flex items-center gap-4">
        {/* Toggle Button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleSidebar}
              className="text-white hover:bg-white/10 hover:text-white"
              title="Alternar Menu"
              aria-label="Alternar Menu"
            >
              <Menu size={24} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Alternar Menu</TooltipContent>
        </Tooltip>

        <div className="flex items-center gap-3">
          <Image
            src="/fai-icone.png"
            alt="FAI • UFSCar"
            width={30}
            height={30}
            className="object-contain"
            priority
          />
          <h1 className="text-white text-xl font-semibold tracking-tight hidden sm:block">
            FAI <span className="font-light opacity-90">• UFSCar</span>
          </h1>
        </div>
      </div>

      {/* Backend Connection Status */}
      <div className="flex items-center gap-2 mr-2">
        {isBackendConnected === true && (
          <Badge
            className="gap-1.5 px-3 py-1 bg-fai-green/15 text-fai-green border border-fai-green/30"
            title="API Conectada"
          >
            <span className="w-2 h-2 rounded-full bg-fai-green animate-pulse"></span>
            <span className="hidden sm:inline">Online</span>
          </Badge>
        )}
        {isBackendConnected === false && (
          <Badge
            variant="destructive"
            className="gap-1.5 px-3 py-1 bg-destructive/15 text-destructive border border-destructive/30"
            title="API Desconectada"
          >
            <WifiOff size={12} />
            <span className="hidden sm:inline">Offline</span>
          </Badge>
        )}
      </div>
    </header>
  );
}
