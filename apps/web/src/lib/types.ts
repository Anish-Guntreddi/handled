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
