"use client";

import { useState } from "react";
import { cn, formatDate, formatDuration, getSeverityColor, getSeverityLabel, getStatusColor, getStatusLabel } from "@/lib/utils";
import { Loader2, ChevronDown, ChevronUp, FileText, AlertCircle, CheckCircle, XCircle, Info, Clock, Brain, Zap, Palette, Building2, TestTube, Copy, ExternalLink, Github, Filter, X } from "lucide-react";

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

interface JobDetailProps {
  job: JobDetailData;
  loading: boolean;
}

const AGENT_ICONS: Record<string, React.ReactNode> = {
  security: <AlertCircle className="h-4 w-4" />,
  performance: <Zap className="h-4 w-4" />,
  style: <Palette className="h-4 w-4" />,
  architecture: <Building2 className="h-4 w-4" />,
  tests: <TestTube className="h-4 w-4" />,
  aggregator: <Brain className="h-4 w-4" />,
};

const AGENT_LABELS: Record<string, string> = {
  security: "Security",
  performance: "Performance",
  style: "Style",
  architecture: "Architecture",
  tests: "Tests",
  aggregator: "Aggregator",
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];

export function JobDetail({ job, loading }: JobDetailProps) {
  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(new Set());
  const [severityFilter, setSeverityFilter] = useState<string[]>([]);
  const [agentFilter, setAgentFilter] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  if (loading && !job.result) {
    return (
      <div className="bg-card border border-border rounded-xl p-8 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!job.result) {
    return (
      <div className="bg-card border border-border rounded-xl p-8">
        <div className="text-center py-8">
          <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">Review Failed</h3>
          <p className="text-muted-foreground">{job.error || "Unknown error occurred"}</p>
        </div>
      </div>
    );
  }

  const { all_findings, summary, stats, agent_results } = job.result;

  // Filter findings
  const filteredFindings = all_findings.filter((finding) => {
    const matchesSeverity = severityFilter.length === 0 || severityFilter.includes(finding.severity);
    const matchesAgent = agentFilter.length === 0 || agentFilter.includes(finding.agent);
    const matchesSearch = searchQuery === "" ||
      finding.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      finding.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      finding.filename.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesAgent && matchesSearch;
  });

  // Sort by severity
  const sortedFindings = [...filteredFindings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );

  // Group by file
  const findingsByFile = sortedFindings.reduce((acc, finding) => {
    if (!acc[finding.filename]) acc[finding.filename] = [];
    acc[finding.filename].push(finding);
    return acc;
  }, {} as Record<string, Finding[]>);

  const toggleFinding = (id: string) => {
    const newSet = new Set(expandedFindings);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setExpandedFindings(newSet);
  };

  const clearFilters = () => {
    setSeverityFilter([]);
    setAgentFilter([]);
    setSearchQuery("");
  };

  const hasActiveFilters = severityFilter.length > 0 || agentFilter.length > 0 || searchQuery !== "";

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <span className="font-mono text-lg font-semibold text-foreground">{job.pr_id}</span>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <span className={cn("px-2 py-0.5 rounded-full", getStatusColor(job.status))}>
                {getStatusLabel(job.status)}
              </span>
              <span>Trigger: {job.trigger}</span>
              <span>Created: {formatDate(job.created_at)}</span>
              {job.started_at && <span>Started: {formatDate(job.started_at)}</span>}
              {job.completed_at && <span>Completed: {formatDate(job.completed_at)}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigator.clipboard.writeText(job.pr_id)}
              className="px-3 py-1.5 text-sm border border-input rounded-lg hover:bg-accent transition-colors flex items-center gap-2"
            >
              <Copy className="h-4 w-4" />
              Copy ID
            </button>
            <a
              href={`https://github.com/${job.pr_id.replace("github:", "").replace("#", "/pull/")}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 text-sm border border-input rounded-lg hover:bg-accent transition-colors flex items-center gap-2"
            >
              <Github className="h-4 w-4" />
              View on GitHub
            </a>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="p-4 border-b border-border">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <StatCard label="Total" value={all_findings.length} icon={FileText} color="text-primary" />
          <StatCard label="Critical" value={stats.critical || 0} icon={AlertCircle} color="text-red-500" />
          <StatCard label="High" value={stats.high || 0} icon={AlertCircle} color="text-orange-500" />
          <StatCard label="Medium" value={stats.medium || 0} icon={AlertCircle} color="text-yellow-500" />
          <StatCard label="Low" value={stats.low || 0} icon={Info} color="text-green-500" />
          <StatCard label="Info" value={stats.info || 0} icon={Info} color="text-blue-500" />
        </div>
        {job.result.total_time_ms && (
          <p className="mt-3 text-sm text-muted-foreground">
            Completed in {formatDuration(job.result.total_time_ms)} • {job.result.total_tokens} tokens
          </p>
        )}
      </div>

      {/* Filters */}
      <div className="p-4 border-b border-border">
        <div className="space-y-3">
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search findings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-input rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {SEVERITY_ORDER.map((sev) => (
              <FilterChip
                key={sev}
                label={getSeverityLabel(sev)}
                selected={severityFilter.includes(sev)}
                onClick={() => setSeverityFilter(prev =>
                  prev.includes(sev) ? prev.filter(s => s !== sev) : [...prev, sev]
                )}
                color={getSeverityColor(sev).replace("bg-", "bg-").replace("500", "100")} // This won't work properly, need better approach
                textColor={getSeverityColor(sev).replace("bg-", "text-")}
              />
            ))}
            {Object.entries(agent_results).map(([agentKey, agentResult]) => (
              <FilterChip
                key={agentKey}
                label={AGENT_LABELS[agentKey] || agentKey}
                count={agentResult.findings.length}
                selected={agentFilter.includes(agentKey)}
                onClick={() => setAgentFilter(prev =>
                  prev.includes(agentKey) ? prev.filter(s => s !== agentKey) : [...prev, agentKey]
                )}
              />
            ))}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="px-3 py-1 text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
              >
                <X className="h-3 w-3" />
                Clear filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Findings */}
      <div className="flex-1 overflow-y-auto p-4">
        {sortedFindings.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-12">
            <CheckCircle className="h-12 w-12 mb-4 text-green-500" />
            <h3 className="text-lg font-medium text-foreground mb-1">No findings</h3>
            <p>{hasActiveFilters ? "Try adjusting your filters" : "Great job! No issues detected."}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(findingsByFile).map(([filename, findings]) => (
              <FileFindingsGroup
                key={filename}
                filename={filename}
                findings={findings}
                expandedFindings={expandedFindings}
                onToggle={toggleFinding}
              />
            ))}
          </div>
        )}
      </div>

      {/* Agent Summaries */}
      <div className="p-4 border-t border-border">
        <h4 className="font-semibold text-foreground mb-3">Agent Summaries</h4>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(agent_results).map(([agentKey, agentResult]) => (
            <AgentSummaryCard
              key={agentKey}
              agentKey={agentKey}
              agentResult={agentResult}
            />
          ))}
        </div>
      </div>

      {/* Overall Summary */}
      <div className="p-4 border-t border-border bg-muted/50">
        <h4 className="font-semibold text-foreground mb-2">Overall Summary</h4>
        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{summary}</p>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ComponentType<{ className?: string }>; color: string }) {
  return (
    <div className="p-3 rounded-lg bg-background border border-border">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
        <Icon className={cn("h-5 w-5", color)} />
      </div>
    </div>
  );
}

function FilterChip({
  label,
  count,
  selected,
  onClick,
  color = "bg-primary/10",
  textColor = "text-primary",
}: {
  label: string;
  count?: number;
  selected: boolean;
  onClick: () => void;
  color?: string;
  textColor?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1",
        selected ? `${color} ${textColor}` : "bg-secondary hover:bg-secondary/80"
      )}
    >
      {label}
      {count !== undefined && (
        <span className={cn("px-1.5 py-0.5 rounded-full text-[10px]", selected ? "bg-background/50" : "bg-background")}>
          {count}
        </span>
      )}
    </button>
  );
}

function FileFindingsGroup({
  filename,
  findings,
  expandedFindings,
  onToggle,
}: {
  filename: string;
  findings: Finding[];
  expandedFindings: Set<string>;
  onToggle: (id: string) => void;
}) {
  const allExpanded = findings.every(f => expandedFindings.has(f.id));
  const anyExpanded = findings.some(f => expandedFindings.has(f.id));

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => findings.forEach(f => onToggle(f.id))}
        className="w-full p-3 bg-muted/50 flex items-center justify-between hover:bg-muted transition-colors"
      >
        <div className="flex items-center gap-3">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="font-mono text-sm font-medium text-foreground">{filename}</span>
          <span className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded">
            {findings.length} finding{findings.length !== 1 ? "s" : ""}
          </span>
        </div>
        {anyExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {anyExpanded && (
        <div className="divide-y divide-border">
          {findings.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              expanded={expandedFindings.has(finding.id)}
              onToggle={() => onToggle(finding.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FindingCard({
  finding,
  expanded,
  onToggle,
}: {
  finding: Finding;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="p-4 hover:bg-muted/30 transition-colors">
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-3 text-left"
      >
        <div className={cn("flex-shrink-0 w-2 h-2 rounded-full mt-1.5", getSeverityColor(finding.severity))} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h5 className="font-medium text-foreground">{finding.title}</h5>
            <span className={cn("px-2 py-0.5 text-xs font-medium rounded-full flex-shrink-0", getSeverityColor(finding.severity))}>
              {getSeverityLabel(finding.severity)}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{finding.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {finding.filename && (
              <span className="font-mono bg-background px-1.5 py-0.5 rounded">{finding.filename}{finding.line_start ? `:${finding.line_start}` : ""}</span>
            )}
            {finding.rule_id && (
              <span className="px-1.5 py-0.5 bg-background rounded">{finding.rule_id}</span>
            )}
            {finding.agent !== "aggregator" && (
              <span className="px-1.5 py-0.5 bg-background rounded capitalize">{finding.agent}</span>
            )}
            <span className="px-1.5 py-0.5 bg-background rounded">Confidence: {(finding.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
      </button>
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border space-y-4">
          {finding.code_snippet && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Code Snippet</p>
              <pre className="bg-neutral-900 text-neutral-100 p-3 rounded text-xs overflow-x-auto font-mono">
                <code>{finding.code_snippet}</code>
              </pre>
            </div>
          )}
          {finding.suggestion && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Suggested Fix</p>
              <pre className="bg-green-900/20 text-green-100 p-3 rounded text-xs overflow-x-auto font-mono">
                <code>{finding.suggestion}</code>
              </pre>
            </div>
          )}
          {finding.references.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">References</p>
              <ul className="space-y-1">
                {finding.references.map((ref, i) => (
                  <li key={i}>
                    <a href={ref} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1">
                      <ExternalLink className="h-3 w-3" />
                      {ref}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentSummaryCard({ agentKey, agentResult }: { agentKey: string; agentResult: AgentResult }) {
  const Icon = AGENT_ICONS[agentKey] ? (() => AGENT_ICONS[agentKey]) : Brain;
  const findingsBySeverity = agentResult.findings.reduce((acc, f) => {
    acc[f.severity] = (acc[f.severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="p-4 bg-background border border-border rounded-lg">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-1.5 bg-primary/10 text-primary rounded">
          <Icon />
        </div>
        <span className="font-medium text-foreground">{AGENT_LABELS[agentKey] || agentKey}</span>
      </div>
      <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{agentResult.summary}</p>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {SEVERITY_ORDER.map(sev => (
          findingsBySeverity[sev] > 0 && (
            <span key={sev} className={cn("px-2 py-0.5 text-xs rounded", getSeverityColor(sev).replace("bg-", "bg-").replace("500", "100"), getSeverityColor(sev).replace("bg-", "text-"))}>
              {findingsBySeverity[sev]} {getSeverityLabel(sev).charAt(0)}
            </span>
          )
        ))}
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatDuration(agentResult.processing_time_ms)}</span>
        <span>{agentResult.tokens_used} tokens • {agentResult.model_used}</span>
      </div>
      {agentResult.errors.length > 0 && (
        <p className="mt-2 text-xs text-red-500">Errors: {agentResult.errors.join(", ")}</p>
      )}
    </div>
  );
}