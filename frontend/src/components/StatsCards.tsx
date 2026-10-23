"use client";

import { cn } from "@/lib/utils";

interface StatsCardsProps {
  counts: Record<string, number>;
  total: number;
}

const STAT_CONFIG = [
  { key: "completed", label: "Completed", color: "bg-green-500", icon: "✓" },
  { key: "in_progress", label: "In Progress", color: "bg-blue-500", icon: "⟳" },
  { key: "pending", label: "Pending", color: "bg-yellow-500", icon: "○" },
  { key: "failed", label: "Failed", color: "bg-red-500", icon: "✕" },
  { key: "skipped", label: "Skipped", color: "bg-gray-500", icon: "—" },
];

export function StatsCards({ counts, total }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      <div className="col-span-2 md:col-span-3 lg:col-span-2 bg-card border border-border rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-3xl font-bold text-foreground">{total}</p>
            <p className="text-sm text-muted-foreground">Total Reviews</p>
          </div>
          <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center">
            <span className="text-2xl font-bold text-primary">{total}</span>
          </div>
        </div>
      </div>
      {STAT_CONFIG.map((stat) => (
        <div
          key={stat.key}
          className="bg-card border border-border rounded-xl p-4"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold text-foreground">
                {counts[stat.key] || 0}
              </p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </div>
            <div
              className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center",
                stat.color
              )}
            >
              <span className="text-white font-bold">{stat.icon}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}