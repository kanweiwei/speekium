import React from 'react';
import { Home, Settings, Info } from 'lucide-react';

interface SidebarProps {
  onOpenSettings: () => void;
}

export function Sidebar({ onOpenSettings }: SidebarProps) {
  const [activeTab, setActiveTab] = React.useState('home');

  const navItems = [
    { id: 'home', icon: Home, label: '主页' },
    { id: 'settings', icon: Settings, label: '设置', onClick: onOpenSettings },
    { id: 'about', icon: Info, label: '关于' },
  ];

  return (
    <div className="w-[180px] h-full bg-card border-r border-border flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center justify-center border-b border-border">
        <div className="text-xl font-semibold">
          <span className="text-primary">🎙️</span>
          <span className="ml-2">Speekium</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => {
                if (item.onClick) {
                  item.onClick();
                } else {
                  setActiveTab(item.id);
                }
              }}
              className={`
                w-full flex items-center gap-3 px-4 py-3 rounded-lg
                transition-colors duration-200
                ${isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                }
              `}
            >
              <Icon className="w-5 h-5" />
              <span className="text-sm font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-muted-foreground text-center">
          v0.1.0
        </div>
      </div>
    </div>
  );
}
