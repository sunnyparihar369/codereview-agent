"use client";

import { useState, useEffect } from "react";
import { Search, Loader2, CheckCircle, AlertCircle, XCircle, Github, ExternalLink, FileText, Filter, RefreshCw } from "lucide-react";
import { JobList } from "@/components/JobList";
import { JobDetail } from "@/components/JobDetail";
import { StatsCards } from "@/components/StatsCards";
import { cn } from "@/lib/utils";

interface Job {
  pr_id: string;
  status: string;
  trigger: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  findings_count: number;
}

interface JobDetailData {
  pr_id: string;
  status: string;
  trigger: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  result: {
    all_findings: Finding[];
    summary: string;
    stats: Record<string, number>;
    agent_results: Record<string, AgentResult>;
  } | null;
}

interface Finding {
  id: string;
  agent: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  filename: string;
  line_start: number | null;
  line_end: number | null;
  code_snippet: string | null;
  suggestion: string | null;
  rule_id: string | null;
  references: string[];
  confidence: number;
  metadata: Record<string, any>;
}

interface AgentResult {
  agent: string;
  findings: Finding[];
  summary: string;
  metadata: Record<string, any>;
  processing_time_ms: number;
  tokens_used: number;
  model_used: string;
  errors: string[];
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
  info: "bg-blue-500",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchJobs = async () => {
    try {
      const res = await fetch(`/api/jobs?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    }
  };

  const fetchJobDetail = async (prId: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(prId)}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedJob(data);
      }
    } catch (err) {
      console.error("Failed to fetch job detail:", err);
    } finally {
      setLoading(false);
    }
  };

  const triggerReview = async (prUrl: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pr_url: prUrl, provider: "github", force: false }),
      });
      if (res.ok) {
        await fetchJobs();
      }
    } catch (err) {
      console.error("Failed to trigger review:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    if (autoRefresh) {
      const interval = setInterval(fetchJobs, 10000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch = job.pr_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || job.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const statusCounts = jobs.reduce(
    (acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Github className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-2xl font-bold text-foreground">CodeReview Agent</h1>
              <p className="text-sm text-muted-foreground">Multi-agent automated code review system</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-input"
              />
              Auto-refresh (10s)
            </label>
            <button
              onClick={fetchJobs}
              disabled={loading}
              className="px-3 py-1.5 text-sm border border-input rounded-lg hover:bg-accent transition-colors flex items-center gap-2"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats Cards */}
        <StatsCards counts={statusCounts} total={jobs.length} />

        {/* Search and Filters */}
        <div className="mb-6 flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search PRs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </select>
        </div>

        {/* Content Area */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Job List */}
          <div className="lg:col-span-1">
            <JobList
              jobs={filteredJobs}
              selectedJob={selectedJob?.pr_id}
              onSelect={fetchJobDetail}
              loading={loading}
            />
          </div>

          {/* Job Detail or Empty State */}
          <div className="lg:col-span-2">
            {selectedJob ? (
              <JobDetail job={selectedJob} loading={loading} />
            ) : (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-center p-8">
                <FileText className="h-16 w-16 text-muted-foreground/50 mb-4" />
                <h2 className="text-xl font-semibold text-foreground mb-2">Select a PR to view details</h2>
                <p className="text-muted-foreground max-w-md">
                  Choose a pull request from the list to see the detailed review findings, 
                  agent summaries, and statistics.
                </p>
                <div className="mt-6 flex gap-4">
                  <button
                    onClick={() => {
                      const url = prompt("Enter GitHub PR URL:");
                      if (url) triggerReview(url);
                    }}
                    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2"
                  >
                    <Github className="h-4 w-4" />
                    Trigger Manual Review
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}