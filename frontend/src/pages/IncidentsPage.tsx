import { recoveryLabel } from '../components/common/recoveryLabel';
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, AlertOctagon, ArrowUpRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

const STATUS_FILTERS = ['ALL', 'RECOVERED', 'NEEDS_ATTENTION', 'EXECUTING', 'RECEIVED'];

export const IncidentsPage: React.FC = () => {
  const { token } = useAuth();
  const [page, setPage] = useState(0);
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const limit = 15;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['incidentsList', token, page, selectedStatus, searchQuery],
    queryFn: () =>
      api.getIncidents(token!, {
        limit,
        offset: page * limit,
        status: selectedStatus === 'ALL' ? undefined : selectedStatus,
        search: searchQuery ? searchQuery : undefined,
      }),
    enabled: !!token,
    refetchInterval: 7000,
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setSearchQuery(searchInput.trim());
  };

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="space-y-8">
      <Header
        title="Incident Management"
        subtitle="Full audit catalog of automated failures, recovery plans, and diagnoses."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        {/* Controls Bar: Search & Status Filters */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl bg-card border border-border shadow-card">
          {/* Status Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSelectedStatus(s);
                  setPage(0);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                  selectedStatus === s
                    ? 'bg-primary-violet text-white shadow-glow-purple font-semibold'
                    : 'bg-elevated/50 text-text-secondary hover:text-text-primary hover:bg-elevated'
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Search Bar */}
          <form onSubmit={handleSearchSubmit} className="relative sm:w-72">
            <Search className="w-4 h-4 text-text-secondary absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search operation, execution, step..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-elevated border border-border text-xs text-text-primary focus:outline-none focus:border-primary-violet transition-colors"
            />
          </form>
        </div>

        {/* Incidents Table Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card overflow-hidden">
          {isLoading ? (
            <LoadingSkeleton rows={8} height="h-12" />
          ) : isError ? (
            <div className="p-8 text-center text-rose-400 text-xs">
              Failed to load incidents from REBOOTX backend.
            </div>
          ) : data?.items.length === 0 ? (
            <EmptyState
              title="No Incidents Found"
              description={
                searchQuery || selectedStatus !== 'ALL'
                  ? 'No failure events match your active filters.'
                  : 'Your automated workflows have not recorded any failure events yet.'
              }
              icon={<AlertOctagon className="w-8 h-8 text-primary-violet" />}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/80 text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">Workflow</th>
                    <th className="py-3 px-3">Failed Step</th>
                    <th className="py-3 px-3">Operation ID</th>
                    <th className="py-3 px-3">Category</th>
                    <th className="py-3 px-3">Diagnosis Summary</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Created</th>
                    <th className="py-3 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {data?.items.map((inc) => (
                    <tr
                      key={inc.id}
                      className="hover:bg-elevated/40 transition-colors group cursor-pointer"
                    >
                      <td className="py-3 px-3 font-medium text-text-primary">
                        {inc.workflow_external_id}
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px] text-text-secondary">
                        {inc.failed_step}
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px] text-text-secondary truncate max-w-[120px]">
                        {inc.operation_id}
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-mono text-[11px] text-primary-violet bg-primary-violet/10 px-2 py-0.5 rounded border border-primary-violet/20">
                          {inc.failure_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-text-secondary truncate max-w-[200px]" title={inc.diagnosis_summary || ''}>
                        {inc.diagnosis_summary || (
                          <span className="text-zinc-500 italic">Pending diagnosis</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={inc.status} size="sm" />
                <div className="text-[10px] text-text-secondary mt-1">{recoveryLabel(inc.recovery_mode, inc.verification_outcome)}</div>
                      </td>
                      <td className="py-3 px-3 text-text-secondary font-mono text-[11px]">
                        {new Date(inc.created_at).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          to={`/incidents/${inc.id}`}
                          className="inline-flex items-center gap-1 text-primary-violet hover:text-primary-pink transition-colors font-medium text-xs"
                        >
                          Details
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-6 mt-4 border-t border-border/80 text-xs text-text-secondary">
              <div>
                Showing <strong className="text-text-primary">{page * limit + 1}</strong> to{' '}
                <strong className="text-text-primary">
                  {Math.min((page + 1) * limit, data?.total || 0)}
                </strong>{' '}
                of <strong className="text-text-primary">{data?.total}</strong> incidents
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="p-1.5 rounded-lg border border-border bg-elevated hover:bg-zinc-800 disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-mono text-xs text-text-primary px-2">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="p-1.5 rounded-lg border border-border bg-elevated hover:bg-zinc-800 disabled:opacity-40 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
