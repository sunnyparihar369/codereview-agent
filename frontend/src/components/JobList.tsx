"use client";

import { cn, formatDate, getStatusColor, getStatusLabel } from "@/lib/utils";
import { ChevronRight, Clock, CheckCircle, XCircle, AlertCircle, Loader2 } from "lucide-react";

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

interface JobListProps {
  jobs: Job[];
  selectedJob: string | null;
  onSelect: (prId: string) => void;
  loading: boolean;
}

export function JobList({ jobs, selectedJob, onSelect, loading }: JobListProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "in_progress":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  if (jobs.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-6">
        <div className="text-center py-8">
          <p className="text-muted-foreground">No reviews found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="p-4 border-b border-border">
        <h3 className="font-semibold text-foreground">Recent Reviews</h3>
      </div>
      <div className="divide-y divide-border">
        {jobs.map((job) => (
          <button
            key={job.pr_id}
            onClick={() => onSelect(job.pr_id)}
            className={cn(
              "w-full p-4 text-left hover:bg-accent transition-colors flex items-start gap-3",
              selectedJob === job.pr_id && "bg-accent border-l-2 border-primary"
            )}
          >
            <div className={cn("flex-shrink-0 mt-0.5", getStatusColor(job.status))}>
              {getStatusIcon(job.status)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "font-mono text-sm font-medium truncate",
                    selectedJob === job.pr_id ? "text-primary" : "text-foreground"
                  )}
                >
                  {job.pr_id}
                </span>
                <span
                  className={cn(
                    "px-2 py-0.5 text-xs font-medium rounded-full flex-shrink-0",
                    getStatusColor(job.status)
                  )}
                >
                  {getStatusLabel(job.status)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDate(job.created_at)}
                </span>
                {job.findings_count > 0 && (
                  <span className="text-primary font-medium">
                    {job.findings_count} findings
                  </span>
                )}
              </div>
              {job.error && (
                <p className="mt-2 text-xs text-red-500 truncate">{job.error}</p>
              )}
            </div>
            <ChevronRight
              className={cn(
                "flex-shrink-0 h-4 w-4 text-muted-foreground",
                selectedJob === job.pr_id && "text-primary"
              )}
            />
          </button>
        ))}
      </div>
      {loading && (
        <div className="p-4 border-t border-border flex justify-center">
          <Loader2 className="h-5 w-5 text-primary animate-spin" />
        </div>
      )}
    </div>
  );
}