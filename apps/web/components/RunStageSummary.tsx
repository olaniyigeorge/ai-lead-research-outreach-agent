import type { ExternalUsage, RunOut } from "@/lib/api-client";

type StageChip = {
  label: string;
  costText: string;
  title: string;
};

function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

function findUsage(usage: ExternalUsage[], stage: string, source: string): ExternalUsage | undefined {
  return usage.find((u) => u.stage === stage && u.source === source);
}

function buildChips(run: RunOut): StageChip[] {
  const icp = run.icp;
  const icpConfirmed = run.status !== "draft" && run.status !== "awaiting_icp_confirmation";
  const chips: StageChip[] = [];

  if (icp) {
    const sanityCost = run.claude_cost_by_stage["sanity_check"];
    chips.push({
      label: "Sanity check",
      costText: sanityCost ? formatCost(sanityCost) : "—",
      title: "Objective passed the plausibility gate before any paid research ran (Haiku).",
    });

    const icpCost = run.claude_cost_by_stage["icp"];
    chips.push({
      label: "ICP refinement",
      costText: icpCost ? formatCost(icpCost) : "—",
      title: `Refined into ${icp.industries.length || 0} industr${icp.industries.length === 1 ? "y" : "ies"}, ${
        icp.assumptions_made.length
      } assumption${icp.assumptions_made.length === 1 ? "" : "s"} flagged for review (Sonnet).`,
    });
  }

  if (icpConfirmed) {
    const discoverySummary =
      run.leads.length > 0
        ? `Found ${run.leads.length} of ${run.lead_count_limit ?? "?"} requested candidate companies.`
        : run.status === "running"
          ? "Searching for candidate companies..."
          : run.status === "failed"
            ? "No candidate companies were found."
            : "Not started yet.";
    const apifyUsage = findUsage(run.external_usage, "discovery", "apify");
    chips.push({
      label: "Discovery",
      costText: apifyUsage?.estimated_cost_usd != null ? `~${formatCost(apifyUsage.estimated_cost_usd)}` : "—",
      title: `${discoverySummary} (Apify${
        apifyUsage ? `, ~$ inferred from its published per-result price for ${apifyUsage.units} result${apifyUsage.units === 1 ? "" : "s"}` : ""
      })`,
    });

    const scrapedCount = run.leads.filter((l) => l.sources.length > 0).length;
    const scrapingSummary =
      run.leads.length === 0
        ? "Not started yet."
        : scrapedCount > 0
          ? `Scraped and summarized ${scrapedCount} of ${run.leads.length} candidate site${run.leads.length === 1 ? "" : "s"}.`
          : "Not started yet.";
    const scrapingClaudeCost = run.claude_cost_by_stage["scraping"];
    const firecrawlUsage = findUsage(run.external_usage, "scraping", "firecrawl");
    const scrapingCostParts = [
      scrapingClaudeCost ? formatCost(scrapingClaudeCost) : null,
      firecrawlUsage ? `${firecrawlUsage.units} credit${firecrawlUsage.units === 1 ? "" : "s"}` : null,
    ].filter(Boolean);
    chips.push({
      label: "Scraping",
      costText: scrapingCostParts.length > 0 ? scrapingCostParts.join(" + ") : "—",
      title: `${scrapingSummary} (Firecrawl credits + Haiku summarization cost)`,
    });

    const primaryLeads = run.leads.filter((l) => !l.is_buffer);
    const qualifiedCount = primaryLeads.filter((l) => l.qualification_status === "qualified").length;
    const disqualifiedCount = primaryLeads.filter((l) => l.qualification_status === "disqualified").length;
    const needsReviewCount = primaryLeads.filter((l) => l.qualification_status === "needs_review").length;
    const decidedCount = qualifiedCount + disqualifiedCount + needsReviewCount;
    const scrapedCountForQual = primaryLeads.filter((l) => l.sources.length > 0).length;
    const qualificationSummary =
      decidedCount > 0
        ? `${qualifiedCount} qualified, ${disqualifiedCount} disqualified, ${needsReviewCount} needs review.`
        : scrapedCountForQual === 0
          ? "Not started yet."
          : run.status === "failed"
            ? "Failed -- see logs."
            : "Not started yet.";
    const qualificationCost = run.claude_cost_by_stage["qualification"];
    chips.push({
      label: "Qualification",
      costText: qualificationCost ? formatCost(qualificationCost) : "—",
      title: `${qualificationSummary} (Sonnet, weighed against the confirmed ICP)`,
    });

    const draftedLeadCount = primaryLeads.filter((l) => l.drafts.length > 0).length;
    const draftingSummary =
      qualifiedCount === 0
        ? "Not started yet."
        : draftedLeadCount > 0
          ? `Drafted outreach for ${draftedLeadCount} of ${qualifiedCount} qualified lead${qualifiedCount === 1 ? "" : "s"}.`
          : run.status === "failed"
            ? "Failed -- see logs."
            : "Not started yet.";
    const draftingCost = run.claude_cost_by_stage["drafting"];
    chips.push({
      label: "Drafting",
      costText: draftingCost ? formatCost(draftingCost) : "—",
      title: `${draftingSummary} (Sonnet, cited to scraped evidence)`,
    });
  }

  return chips;
}

export function RunStageSummary({ run }: { run: RunOut }) {
  const chips = buildChips(run);
  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {chips.map((chip, i) => (
        <span key={chip.label} className="flex items-center gap-4">
          <span className="text-xs text-muted-text" title={chip.title}>
            <span className="font-medium text-foreground">{chip.label}:</span> {chip.costText}
          </span>
          {i < chips.length - 1 && <span className="hidden text-surface-border sm:inline">|</span>}
        </span>
      ))}
      {run.total_run_cost_usd > 0 && (
        <span className="text-xs font-medium text-foreground" title="Claude spend (exact) + inferred Apify spend -- Firecrawl is tracked in credits, not dollars, so it isn't in this figure.">
          Total run spend: {formatCost(run.total_run_cost_usd)}
        </span>
      )}
    </div>
  );
}
