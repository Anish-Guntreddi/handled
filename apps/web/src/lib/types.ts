// Wire types mirror the backend's camelCase responses (PRD §9).

export type Tokens = {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
};

export type User = {
  id: string;
  email: string;
  fullName: string | null;
};

export type OrgMembershipSummary = {
  orgId: string;
  name: string;
  role: string;
  plan: string;
};

export type Me = {
  user: User;
  orgs: OrgMembershipSummary[];
};

export type Org = {
  id: string;
  name: string;
  uei: string | null;
  plan: string;
  role: string | null;
  createdAt?: string;
};

export type CompanyProfile = {
  orgId: string;
  websiteUrl: string | null;
  industry: string | null;
  location: string | null;
  description: string | null;
  services: { name: string; description: string }[];
  naicsGuesses: { code: string; label: string; confidence: number }[];
  fundingCategories: string[];
  targetCustomers: string[];
  certifications: { name: string; status: string }[];
  capabilityStatement: string | null;
  missingFields: string[];
  evidenceCount: number;
};

export type WorkflowRunCreated = { workflowRunId: string };

export type WorkflowRun = {
  id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "needs_input";
  steps: { name: string; status: string }[];
  partialResults?: Record<string, unknown>;
  timeSavedMinutes?: number | null;
  error?: string | null;
};

export type DocumentItem = {
  id: string;
  filename: string;
  mimeType: string | null;
  sourceKind: string;
  parseStatus: string;
  chunkCount: number;
  pageCount: number | null;
};

export type OpportunitySummary = {
  id: string;
  kind: string;
  title: string;
  sponsor: string | null;
  deadline: string | null;
  fitScore: number | null;
  decisionHint: string | null;
  sourceUrl: string | null;
};

export type FitRationale = { for: string[]; against: string[]; key_factors: string[] };

export type OpportunityDetail = OpportunitySummary & {
  externalId: string | null;
  fitRationale: FitRationale | null;
  details: Record<string, unknown> & {
    research?: { agency_summary: string; prior_awards_summary: string; risk_level: string };
    set_aside?: string | null;
    naics?: string;
  };
  rawText: string | null;
};

export type FilingResponse = {
  id: string;
  opportunityId: string;
  kind: string;
  status: string;
  ownerUserId: string | null;
  createdAt?: string;
};

export type RequirementResponse = {
  id: string;
  text: string;
  category: string;
  mandatory: boolean;
  locator: string | null;
  needsReview: boolean;
  sourceId: string | null;
};

export type FilingAggregate = {
  filing: FilingResponse;
  opportunity: OpportunitySummary | null;
  requirements: RequirementResponse[];
  requirementCount: number;
  status: string;
};
