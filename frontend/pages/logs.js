import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

import { deleteLog, fetchLogs } from '../utils/api';

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  return new Date(value).toLocaleString();
}

function riskClass(level) {
  if (level === 'malicious') return 'risk-pill-malicious';
  if (level === 'suspicious') return 'risk-pill-suspicious';
  return 'risk-pill-normal';
}

export default function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [limit, setLimit] = useState(100);
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('all');

  function exportFilteredCsv() {
    if (filteredLogs.length === 0) {
      setStatus('No rows to export for current filters.');
      return;
    }

    const headers = [
      'id',
      'row_index',
      'attack_type',
      'final_attack_type',
      'risk_level',
      'risk_reason',
      'confidence',
      'anomaly_score',
      'is_anomaly',
      'created_at',
    ];

    const csvRows = [headers.join(',')];
    for (const row of filteredLogs) {
      const values = headers.map((key) => {
        const value = row[key] ?? '';
        const safe = String(value).replace(/"/g, '""');
        return `"${safe}"`;
      });
      csvRows.push(values.join(','));
    }

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `threatsense-logs-${Date.now()}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    setStatus(`Exported ${filteredLogs.length} rows to CSV.`);
  }

  async function loadLogs(currentLimit = limit) {
    setIsLoading(true);
    try {
      const data = await fetchLogs(currentLimit);
      setLogs(data.logs || []);
      setStatus(`Loaded ${data.count} logs.`);
    } catch (error) {
      setStatus(`Failed to load logs: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteLog(id);
      setStatus(`Deleted log #${id}.`);
      await loadLogs();
    } catch (error) {
      setStatus(`Delete failed: ${error.message}`);
    }
  }

  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredLogs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return logs.filter((row) => {
      const rowRisk = row.risk_level === 'malicious' ? 'malicious' : row.risk_level === 'suspicious' ? 'suspicious' : 'normal';
      if (riskFilter !== 'all' && rowRisk !== riskFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const text = [row.id, row.attack_type, row.final_attack_type, row.risk_level, row.risk_reason]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return text.includes(normalizedQuery);
    });
  }, [logs, query, riskFilter]);

  const summary = useMemo(() => {
    const counts = { malicious: 0, suspicious: 0, normal: 0 };
    for (const row of filteredLogs) {
      if (row.risk_level === 'malicious') {
        counts.malicious += 1;
      } else if (row.risk_level === 'suspicious') {
        counts.suspicious += 1;
      } else {
        counts.normal += 1;
      }
    }
    return counts;
  }, [filteredLogs]);

  return (
    <>
      <Head>
        <title>ThreatSense Logs</title>
      </Head>

      <main className="min-h-screen px-4 py-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
          <section className="glass-panel flex flex-col gap-4 p-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="mono-label">Prediction Ledger</p>
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-50 md:text-4xl">ThreatSense Logs</h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-300 md:text-base">
                Search, filter, and inspect every prediction row stored by the backend. Delete entries when you need a clean audit trail.
              </p>
            </div>

            <Link
              href="/"
              className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:-translate-y-0.5 hover:bg-white/10"
            >
              Back to dashboard
            </Link>
          </section>

          <section className="glass-card p-5">
            <div className="grid gap-4 lg:grid-cols-[1fr_auto_auto_auto] lg:items-end">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-200">Rows</span>
                <select
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-300"
                >
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                  <option value={500}>500</option>
                </select>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-200">Risk</span>
                <select
                  value={riskFilter}
                  onChange={(event) => setRiskFilter(event.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-300"
                >
                  <option value="all">All</option>
                  <option value="malicious">Malicious</option>
                  <option value="suspicious">Suspicious</option>
                  <option value="normal">Normal</option>
                </select>
              </label>

              <label className="block lg:min-w-[280px]">
                <span className="mb-2 block text-sm font-medium text-slate-200">Search</span>
                <input
                  type="text"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="attack type, reason, id"
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-300"
                />
              </label>

              <button
                type="button"
                className="rounded-full bg-gradient-to-r from-cyan-300 via-cyan-400 to-emerald-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={() => loadLogs(limit)}
                disabled={isLoading}
              >
                {isLoading ? 'Loading…' : 'Refresh'}
              </button>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-300">
              {status ? <span className="soft-chip">{status}</span> : null}
              <span className="soft-chip">Showing {filteredLogs.length} of {logs.length} loaded rows</span>
              <span className="soft-chip risk-pill-malicious">Malicious {summary.malicious}</span>
              <span className="soft-chip risk-pill-suspicious">Suspicious {summary.suspicious}</span>
              <span className="soft-chip risk-pill-normal">Normal {summary.normal}</span>
              <button
                type="button"
                onClick={exportFilteredCsv}
                className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100 transition hover:bg-cyan-400/20"
              >
                Export filtered CSV
              </button>
            </div>
          </section>

          <section className="glass-panel p-5">
            <div className="overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                <thead className="bg-white/5 text-slate-300">
                  <tr>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">ID</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Row</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Model Label</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Final Label</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Risk</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Reason</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Confidence</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Anomaly Score</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Is Anomaly</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Created</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {filteredLogs.length > 0 ? (
                    filteredLogs.map((row) => (
                      <tr key={row.id} className="bg-slate-950/30 transition hover:bg-white/5">
                        <td className="px-4 py-3 font-mono text-cyan-100">#{row.id}</td>
                        <td className="px-4 py-3 text-slate-200">{row.row_index}</td>
                        <td className="px-4 py-3 text-slate-200">{row.attack_type}</td>
                        <td className="px-4 py-3 text-slate-100">{row.final_attack_type || row.attack_type}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${riskClass(row.risk_level)}`}>
                            {row.risk_level || 'normal'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{row.risk_reason || '-'}</td>
                        <td className="px-4 py-3 font-mono text-slate-100">{formatPercent(row.confidence || 0)}</td>
                        <td className="px-4 py-3 font-mono text-slate-100">{(row.anomaly_score ?? 0).toFixed(4)}</td>
                        <td className="px-4 py-3 text-slate-300">{row.is_anomaly ? 'Yes' : 'No'}</td>
                        <td className="px-4 py-3 text-slate-300">{formatDateTime(row.created_at)}</td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            className="rounded-full border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-rose-100 transition hover:bg-rose-400/20"
                            onClick={() => handleDelete(row.id)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={11} className="px-4 py-8 text-center text-slate-300">
                        No records found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
