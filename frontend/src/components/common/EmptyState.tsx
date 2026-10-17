import React, { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl bg-card border border-border/60">
      <div className="p-4 rounded-2xl bg-elevated border border-border text-text-secondary mb-4">
        {icon || <Inbox className="w-8 h-8 text-primary-violet" />}
      </div>
      <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
      <p className="text-sm text-text-secondary max-w-sm mb-5">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};

