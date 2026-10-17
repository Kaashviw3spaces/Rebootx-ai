import React from 'react';

export const LoadingSkeleton: React.FC<{ rows?: number; height?: string }> = ({
  rows = 3,
  height = 'h-10',
}) => {
  return (
    <div className="w-full space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`w-full bg-elevated/60 border border-border/40 rounded-xl ${height}`}
        />
      ))}
    </div>
  );
};

