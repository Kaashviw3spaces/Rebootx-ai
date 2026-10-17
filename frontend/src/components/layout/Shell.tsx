import React, { ReactNode } from 'react';
import { Sidebar } from './Sidebar';

interface ShellProps {
  children: ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ children }) => {
  return (
    <div className="min-h-screen bg-background text-text-primary flex">
      {/* Ambient background glow */}
      <div className="ambient-glow" />

      {/* Fixed Sidebar */}
      <Sidebar />

      {/* Scrollable Main View */}
      <div className="flex-1 ml-64 flex flex-col min-w-0 z-10">
        <main className="flex-1 pb-16">
          {children}
        </main>
      </div>
    </div>
  );
};

