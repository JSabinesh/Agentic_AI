"use client";

import React from "react";
import { Briefcase, Mic2, BookOpen, Radar } from "lucide-react";
import { cn } from "@/lib/utils";

export type FeatureTab = "chat" | "job-match" | "interview" | "resources" | "job-finder";

interface Tab {
  id: FeatureTab;
  label: string;
  icon: React.ElementType;
  description: string;
}

const TABS: Tab[] = [
  {
    id: "chat",
    label: "Career Chat",
    icon: Briefcase,
    description: "Main AI agent",
  },
  {
    id: "job-match",
    label: "Job Match",
    icon: Briefcase,
    description: "Analyse role fit",
  },
  {
    id: "interview",
    label: "Interview Sim",
    icon: Mic2,
    description: "Practice sessions",
  },
  {
    id: "resources",
    label: "Resources",
    icon: BookOpen,
    description: "Guides & tools",
  },
  {
    id: "job-finder",
    label: "Job Finder",
    icon: Radar,
    description: "Opportunity Radar",
  },
];

interface FeatureTabsProps {
  active: FeatureTab;
  onChange: (tab: FeatureTab) => void;
}

export function FeatureTabs({ active, onChange }: FeatureTabsProps) {
  return (
    <nav
      aria-label="Feature tabs"
      className="flex h-[52px] shrink-0 items-stretch gap-0.5 border-b border-border bg-surface px-3"
    >
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            aria-selected={isActive}
            role="tab"
            title={tab.description}
            className={cn(
              "relative flex items-center gap-2 rounded-t-[8px] px-3.5 text-[13px] font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-brand-accent focus-visible:outline-offset-[-2px]",
              isActive
                ? "text-primary after:absolute after:inset-x-1 after:bottom-0 after:h-[2px] after:rounded-full after:bg-brand-accent"
                : "text-secondary hover:bg-surface3 hover:text-primary"
            )}
          >
            <Icon
              className={cn(
                "size-[15px] shrink-0",
                isActive ? "text-brand-accent" : "text-tertiary"
              )}
              strokeWidth={1.8}
            />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
