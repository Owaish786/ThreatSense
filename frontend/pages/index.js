import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { ArcElement, Chart as ChartJS, Legend, Tooltip } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';

import { deleteLog, fetchHealth, fetchLogs, fetchStats, uploadCsv } from '../utils/api';

ChartJS.register(ArcElement, Tooltip, Legend);

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value) {
  if (typeof value !== 'number') {
    return '--';
  }
  return new Intl.NumberFormat().format(value);
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  return new Date(value).toLocaleString();
}

function shortHash(value) {
  if (!value) {
    return '--';
  }
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function riskClass(level) {
  if (level === 'malicious') return 'risk-pill-malicious';
  if (level === 'suspicious') return 'risk-pill-suspicious';
  return 'risk-pill-normal';
}

function tabToRisk(tab) {
  if (tab === 'malicious') return 'malicious';
  if (tab === 'suspicious') return 'suspicious';
  return 'normal';
}

export default function Home() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');
  const [lastBatch, setLastBatch] = useState(null);
  const [stats, setStats] = useState(null);
  const [recentLogs, setRecentLogs] = useState([]);
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [isAutoRefreshOn, setIsAutoRefreshOn] = useState(false);
  const [activeAlertTab, setActiveAlertTab] = useState('all');
  const [copiedField, setCopiedField] = useState('');
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isDeletingLogId, setIsDeletingLogId] = useState(null);

  async function refreshDashboard() {
    try {
      const [statsData, logsData] = await Promise.all([fetchStats(), fetchLogs(25)]);
      setStats(statsData);
      setRecentLogs(logsData.logs || []);
    } catch (error) {
      setStats(null);
      setRecentLogs([]);
      setUploadMessage(`Could not load dashboard data: ${error.message}`);
    }
  }

  async function refreshHealth() {
    try {
      const data = await fetchHealth();
      setBackendHealthy(data?.status === 'ok');
    } catch (_error) {
      setBackendHealthy(false);
    }
  }

  useEffect(() => {
    refreshDashboard();
    refreshHealth();
  }, []);

  useEffect(() => {
    if (!isAutoRefreshOn) {
      return undefined;
    }

    const intervalId = setInterval(() => {
      refreshDashboard();
      refreshHealth();
    }, 15000);

    return () => clearInterval(intervalId);
  }, [isAutoRefreshOn]);

  useEffect(() => {
    if (!copiedField) {
      return undefined;
    }
    const timeoutId = setTimeout(() => setCopiedField(''), 1400);
    return () => clearTimeout(timeoutId);
  }, [copiedField]);

  useEffect(() => {
    function onKeyDown(event) {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
      if (!isShortcut) {
        return;
      }
      event.preventDefault();
      setIsPaletteOpen((prev) => !prev);
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  async function handleCopy(label, value) {
    if (!value || typeof navigator === 'undefined' || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(value);
    setCopiedField(label);
  }

  async function handleUpload(event) {
    event.preventDefault();
    setUploadMessage('');

    if (!selectedFile) {
      setUploadMessage('Please choose a CSV file first.');
      return;
    }

    setIsUploading(true);
    setActiveAlertTab('all');
    try {
      const data = await uploadCsv(selectedFile);
      setLastBatch(data);
      await refreshDashboard();
      setUploadMessage(
        `Processed ${data.count} rows. Known attacks: ${data.summary.known_attacks}, suspicious: ${data.summary.suspicious}, anomalies: ${data.summary.anomalies}.`
      );
    } catch (error) {
      const payload = error?.response?.data;
      const missing = payload?.missing_columns;
      const suffix = Array.isArray(missing) && missing.length > 0
        ? ` Missing columns: ${missing.slice(0, 6).join(', ')}${missing.length > 6 ? '...' : ''}`
        : '';
      const headersPreview = Array.isArray(payload?.received_columns) && payload.received_columns.length > 0
        ? ` Received headers: ${payload.received_columns.slice(0, 4).join(', ')}${payload.received_columns.length > 4 ? '...' : ''}`
        : '';
      const hintText = payload?.hint ? ` Hint: ${payload.hint}` : '';
      const message = payload?.error || error.message;
      setUploadMessage(`Upload failed: ${message}`);
      if (suffix) {
        setUploadMessage(`Upload failed: ${message}.${suffix}${headersPreview ? ` ${headersPreview}.` : ''}${hintText}`);
      } else if (headersPreview || hintText) {
        setUploadMessage(`Upload failed: ${message}. ${headersPreview}${headersPreview && hintText ? ' ' : ''}${hintText}`);
      }
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteFromDashboard(id) {
    const confirmed = window.confirm(`Delete log #${id}?`);
    if (!confirmed) {
      return;
    }

    setIsDeletingLogId(id);
    try {
      await deleteLog(id);
      await refreshDashboard();
      setUploadMessage(`Deleted log #${id}.`);
    } catch (error) {
      setUploadMessage(`Delete failed for #${id}: ${error.message}`);
    } finally {
      setIsDeletingLogId(null);
    }
  }

  async function handleLoadData() {
    try {
      await refreshDashboard();
      await refreshHealth();
      setUploadMessage('Dashboard refreshed from backend.');
    } catch (error) {
      setUploadMessage(`Could not load dashboard data: ${error.message}`);
    }
  }

  const filteredRecentLogs = useMemo(() => {
    if (activeAlertTab === 'all') {
      return recentLogs;
    }

    const risk = tabToRisk(activeAlertTab);
    return recentLogs.filter((row) => {
      if (risk === 'normal') {
        return row.risk_level !== 'malicious' && row.risk_level !== 'suspicious';
      }
      return row.risk_level === risk;
    });
  }, [activeAlertTab, recentLogs]);

  const chartData = useMemo(() => {
    const counts = filteredRecentLogs.reduce((acc, item) => {
      const key = item.final_attack_type || item.attack_type;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    return {
      labels: Object.keys(counts),
      datasets: [
        {
          data: Object.values(counts),
          backgroundColor: ['#67e8f9', '#f97316', '#22c55e', '#a78bfa', '#f43f5e', '#eab308'],
          borderColor: 'rgba(15, 23, 42, 0.9)',
          borderWidth: 4,
          hoverOffset: 8,
        },
      ],
    };
  }, [filteredRecentLogs]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: '64%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#cbd5e1',
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 18,
            boxWidth: 10,
          },
        },
      },
    }),
    []
  );

  const riskSummary = useMemo(() => {
    const summary = { malicious: 0, suspicious: 0, normal: 0 };

    for (const log of recentLogs) {
      if (log.risk_level === 'malicious') {
        summary.malicious += 1;
      } else if (log.risk_level === 'suspicious') {
        summary.suspicious += 1;
      } else {
        summary.normal += 1;
      }
    }

    return summary;
  }, [recentLogs]);

  const attackRate = useMemo(() => {
    if (!stats?.total_scanned) {
      return '--';
    }
    return formatPercent((stats.known_attacks || 0) / stats.total_scanned);
  }, [stats]);

  const currentBatchRows = lastBatch?.results || [];

  const paletteActions = [
    {
      id: 'refresh-now',
      label: 'Refresh Dashboard Now',
      hint: 'Fetch latest stats and logs',
      run: async () => {
        await handleLoadData();
      },
    },
    {
      id: 'toggle-auto-refresh',
      label: isAutoRefreshOn ? 'Disable Auto Refresh' : 'Enable Auto Refresh',
      hint: 'Toggle live updates every 15 seconds',
      run: async () => {
        setIsAutoRefreshOn((prev) => !prev);
      },
    },
    {
      id: 'show-all-alerts',
      label: 'Show All Alerts',
      hint: 'Reset risk tab filter',
      run: async () => {
        setActiveAlertTab('all');
      },
    },
    {
      id: 'focus-upload',
      label: 'Open File Picker',
      hint: 'Choose a CSV for prediction',
      run: async () => {
        const input = document.querySelector('input[type="file"]');
        if (input) {
          input.click();
        }
      },
    },
    {
      id: 'go-to-logs',
      label: 'Go To Logs Page',
      hint: 'Open full prediction log table',
      run: async () => {
        window.location.href = '/logs';
      },
    },
  ];

  return (
    <>
      <Head>
        <title>ThreatSense Command Center</title>
      </Head>

      <main className="min-h-screen px-4 py-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
          <section className="glass-panel spotlight-card flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <p className="mono-label">Live Security Posture</p>
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-50 md:text-4xl">
                ThreatSense Command Center
              </h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-300 md:text-base">
                Upload NSL-KDD-style CSV traffic, run hybrid inference, and review attack, anomaly, and risk signals in one place.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="soft-chip border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
                <span className={`neon-dot ${backendHealthy ? 'online' : 'offline'}`} />
                Backend {backendHealthy ? 'online' : 'offline'}
              </span>

              <button
                type="button"
                onClick={() => setIsAutoRefreshOn((prev) => !prev)}
                className={`soft-chip ${isAutoRefreshOn ? 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100' : ''}`}
              >
                Auto-refresh
                <span className={`toggle-track ${isAutoRefreshOn ? 'toggle-on' : ''}`}>
                  <span className="toggle-thumb" />
                </span>
              </button>

              <button
                type="button"
                onClick={handleLoadData}
                className="rounded-full border border-cyan-400/30 bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5 hover:bg-cyan-200"
              >
                Refresh dashboard
              </button>
              <button
                type="button"
                onClick={() => setIsPaletteOpen(true)}
                className="rounded-full border border-fuchsia-300/30 bg-fuchsia-400/10 px-5 py-3 text-sm font-semibold text-fuchsia-100 transition hover:-translate-y-0.5 hover:bg-fuchsia-400/20"
              >
                Quick actions (Cmd/Ctrl + K)
              </button>
              <Link
                href="/logs"
                className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:-translate-y-0.5 hover:bg-white/10"
              >
                Open logs
              </Link>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {[
              ['Total Scanned', formatNumber(stats?.total_scanned), 'All processed rows'],
              ['Known Attacks', formatNumber(stats?.known_attacks), `Attack rate ${attackRate}`],
              ['Anomalies', formatNumber(stats?.anomalies), 'Isolation forest flagged'],
              ['Suspicious', formatNumber(stats?.suspicious), 'Low-confidence or rule-based'],
              ['Model Version', stats?.model_version ?? '--', 'Loaded artifact version'],
            ].map(([label, value, note]) => (
              <article key={label} className="glass-card p-5">
                <p className="mono-label">{label}</p>
                <p className="mt-3 text-3xl font-bold text-slate-50">{value}</p>
                <p className="mt-2 text-sm text-slate-300">{note}</p>
              </article>
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            <article className="glass-panel p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
                <div>
                  <p className="mono-label">Upload & Predict</p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-50">Analyze a CSV batch</h2>
                  <p className="mt-2 max-w-2xl text-sm text-slate-300">
                    Select a CSV file that matches the NSL-KDD feature set. The backend validates the schema, runs inference, and returns a deterministic batch signature.
                  </p>
                </div>

                {selectedFile ? (
                  <div className="soft-chip border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
                    {selectedFile.name}
                  </div>
                ) : (
                  <div className="soft-chip">Tip: use your existing test_data.csv file.</div>
                )}
              </div>

              <form onSubmit={handleUpload} className="mt-6 space-y-4">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-slate-200">CSV file</span>
                  <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-cyan-400/30 bg-slate-950/60 p-4 md:flex-row md:items-center md:justify-between">
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                      className="block w-full cursor-pointer rounded-xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-300 file:mr-4 file:rounded-full file:border-0 file:bg-cyan-300 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-950 hover:file:bg-cyan-200"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedFile(null)}
                        className="rounded-full border border-white/10 px-4 py-3 text-sm font-medium text-slate-200 transition hover:bg-white/10"
                      >
                        Clear
                      </button>
                      <button
                        type="submit"
                        disabled={isUploading}
                        className="rounded-full bg-gradient-to-r from-cyan-300 via-cyan-400 to-emerald-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isUploading ? 'Running inference…' : 'Run prediction'}
                      </button>
                    </div>
                  </div>
                </label>
              </form>

              {uploadMessage ? (
                <div className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50">
                  {uploadMessage}
                </div>
              ) : null}

              {lastBatch ? (
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="mono-label">Last batch</p>
                    <p className="mt-2 text-2xl font-bold text-slate-50">{lastBatch.count}</p>
                    <p className="mt-1 text-sm text-slate-300">Rows returned by the latest upload.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="mono-label">Input rows</p>
                    <p className="mt-2 text-2xl font-bold text-slate-50">{lastBatch.input_rows ?? lastBatch.count}</p>
                    <p className="mt-1 text-sm text-slate-300">Rows parsed from the file.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="mono-label">Upload hash</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <p className="font-mono text-sm text-cyan-100">{shortHash(lastBatch.upload_sha256)}</p>
                      <button
                        type="button"
                        onClick={() => handleCopy('upload', lastBatch.upload_sha256)}
                        className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200 transition hover:bg-white/10"
                      >
                        {copiedField === 'upload' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <p className="mt-1 text-sm text-slate-300">Use this to verify file identity.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="mono-label">Batch signature</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <p className="font-mono text-sm text-cyan-100">{shortHash(lastBatch.batch_signature)}</p>
                      <button
                        type="button"
                        onClick={() => handleCopy('batch', lastBatch.batch_signature)}
                        className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200 transition hover:bg-white/10"
                      >
                        {copiedField === 'batch' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <p className="mt-1 text-sm text-slate-300">Same file, same outputs.</p>
                  </div>
                </div>
              ) : null}
            </article>

            <article className="glass-panel p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="mono-label">Distribution</p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-50">Recent label mix</h2>
                </div>
                <div className="soft-chip border-amber-300/20 bg-amber-300/10 text-amber-100">
                  Filter-aware view
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {['all', 'malicious', 'suspicious', 'normal'].map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveAlertTab(tab)}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                      activeAlertTab === tab
                        ? 'border-cyan-300/40 bg-cyan-400/10 text-cyan-100'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              <div className="mt-6 h-[340px]">
                {chartData.labels.length === 0 ? (
                  <div className="flex h-full items-center justify-center rounded-3xl border border-white/10 bg-slate-950/40 text-sm text-slate-300">
                    No records for this filter.
                  </div>
                ) : (
                  <Doughnut data={chartData} options={chartOptions} />
                )}
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <span className="soft-chip risk-pill-malicious">Malicious: {riskSummary.malicious}</span>
                <span className="soft-chip risk-pill-suspicious">Suspicious: {riskSummary.suspicious}</span>
                <span className="soft-chip risk-pill-normal">Normal: {riskSummary.normal}</span>
              </div>
            </article>
          </section>

          <section className="glass-panel p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="mono-label">Recent Alerts</p>
                <h2 className="mt-2 text-2xl font-bold text-slate-50">Latest backend predictions</h2>
              </div>
              <Link href="/logs" className="text-sm font-semibold text-cyan-200 transition hover:text-cyan-100">
                View all logs →
              </Link>
            </div>

            <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                <thead className="bg-white/5 text-slate-300">
                  <tr>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">ID</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Model Label</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Final Label</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Risk</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Reason</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Confidence</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Anomaly</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Timestamp</th>
                    <th className="px-4 py-3 font-semibold uppercase tracking-[0.18em]">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {filteredRecentLogs.length > 0 ? (
                    filteredRecentLogs.map((row) => (
                      <tr key={row.id} className="bg-slate-950/30 transition hover:bg-white/5">
                        <td className="px-4 py-3 font-mono text-cyan-100">#{row.id}</td>
                        <td className="px-4 py-3 text-slate-200">{row.attack_type}</td>
                        <td className="px-4 py-3 text-slate-100">{row.final_attack_type || row.attack_type}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${riskClass(row.risk_level)}`}>
                            {row.risk_level || 'normal'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{row.risk_reason || '-'}</td>
                        <td className="px-4 py-3 font-mono text-slate-100">{formatPercent(row.confidence || 0)}</td>
                        <td className="px-4 py-3 text-slate-300">{row.is_anomaly ? 'Yes' : 'No'}</td>
                        <td className="px-4 py-3 text-slate-300">{formatDateTime(row.created_at)}</td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => handleDeleteFromDashboard(row.id)}
                            disabled={isDeletingLogId === row.id}
                            className="rounded-full border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-rose-100 transition hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isDeletingLogId === row.id ? 'Deleting…' : 'Delete'}
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-slate-300">
                        No logs for this risk filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {currentBatchRows.length > 0 ? (
            <section className="glass-panel p-5">
              <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
                <div>
                  <p className="mono-label">Latest Upload Preview</p>
                  <h2 className="mt-2 text-2xl font-bold text-slate-50">Exact returned batch</h2>
                </div>
                <p className="text-sm text-slate-300">Showing the first four rows from the latest response.</p>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {currentBatchRows.slice(0, 4).map((row) => (
                  <article key={`${row.row_index}-${row.id ?? 'pending'}`} className="glass-card p-4">
                    <p className="mono-label">Row {row.row_index}</p>
                    <p className="mt-2 text-xl font-bold text-slate-50">{row.final_attack_type || row.attack_type}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${riskClass(row.risk_level)}`}>
                        {row.risk_level || 'normal'}
                      </span>
                    </div>
                    <p className="mt-3 text-sm text-slate-300">Confidence {formatPercent(row.confidence || 0)}</p>
                    <p className="mt-1 text-sm text-slate-300">Anomaly {row.is_anomaly ? 'Yes' : 'No'}</p>
                    <p className="mt-1 text-sm text-slate-300">{row.risk_reason || 'No special risk rule'}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {isPaletteOpen ? (
            <section className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/75 px-4 pt-20 backdrop-blur-sm">
              <div className="glass-panel w-full max-w-2xl p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="mono-label">Command Palette</p>
                    <h3 className="mt-1 text-xl font-bold text-slate-50">Quick Actions</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsPaletteOpen(false)}
                    className="rounded-full border border-white/10 px-3 py-1 text-sm text-slate-200 hover:bg-white/10"
                  >
                    Close
                  </button>
                </div>

                <div className="grid gap-2">
                  {paletteActions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={async () => {
                        await action.run();
                        setIsPaletteOpen(false);
                      }}
                      className="flex w-full items-start justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
                    >
                      <span>
                        <span className="block text-sm font-semibold text-slate-100">{action.label}</span>
                        <span className="block text-xs text-slate-400">{action.hint}</span>
                      </span>
                      <span className="text-xs text-cyan-200">Run</span>
                    </button>
                  ))}
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </main>
    </>
  );
}
