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
  employees: string | null;
  revenue: string | null;
  ownership: string[];
  activities: string[];
};

export type WorkflowRunCreated = { workflowRunId: string };

export type WorkflowRunSummary = {
  id: string;
  type: string;
  status: string;
  filingId: string | null;
  timeSavedMinutes: number | null;
  inputTokens: number;
  outputTokens: number;
  stepCount: number;
  createdAt?: string;
};

export type AuditEventResponse = {
  id: string;
  action: string;
  actor: string;
  actorId: string | null;
  model: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  status: string | null;
  filingId: string | null;
  runId: string | null;
  occurredAt?: string;
};

export type AuditMetrics = {
  filings: number;
  runs: number;
  succeededRuns: number;
  runsByType: Record<string, number>;
  totalTimeSavedMinutes: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  estimatedCostUsd: number;
  costPerFilingUsd: number;
};

export type BillingStatus = {
  plan: string;
  subscriptionStatus: string | null;
  entitlements: string[];
  premiumFeatures: string[];
  products: Record<string, number>;
};

export type CheckoutResponse = {
  sessionId: string;
  url: string;
  product: string;
  amountCents: number;
  completed: boolean;
};

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

export type ComplianceRow = {
  requirementId: string;
  requirement: string;
  category: string;
  mandatory: boolean;
  locator: string | null;
  sourceId: string | null;
  status: string;
  score: number;
  evidence: string | null;
  evidenceItemId: string | null;
  rationale: string | null;
};

export type RecommendationDetail = {
  decision: string | null;
  score: number | null;
  rationale: { for: string[]; against: string[]; key_gaps: string[] } | null;
  approved: boolean;
};

export type ApprovalItem = {
  target: string;
  decision: string;
  notes: string | null;
  createdAt?: string;
};

export type GeneratedDocSummary = {
  id: string;
  type: string;
  version: number;
  status: string;
  citationValidated: boolean;
  citationCount: number;
  contentMd: string | null;
};

export type PackageView = {
  filingId: string;
  status: string;
  version: number | null;
  documents: GeneratedDocSummary[];
  allCitationsValid: boolean;
  canApprove: boolean;
  canExport: boolean;
};

// Find feed (discovery): the org-scoped "money on the table" payoff surface.
export type DiscoveryItem = {
  id: string;
  kind: "program" | "gov_contract" | "grant";
  typeLabel: string;
  name: string;
  funder: string | null;
  eligibility: "qualify" | "likely";
  eligibilityLabel: string;
  isNew: boolean;
  why: string | null;
  citation: string | null;
  benefit: string | null;
  estValue: number;
  cta: string;
};

export type Discovery = {
  totalEstimate: number;
  programsCount: number;
  contractsCount: number;
  matchCount: number;
  qualifyCount: number;
  likelyCount: number;
  scanCount: number;
  newCount: number;
  items: DiscoveryItem[];
};

// Copilot: the cited Q&A surface over the Company Brain + live program scan.
// POST /orgs/{orgId}/copilot/ask {question} → this shape.
export type CopilotCitation = {
  label: string;
  locator: string;
  snippet: string;
};

export type CopilotCard = {
  name: string;
  citation: string | null;
  benefit: string | null;
  eligibility: "qualify" | "likely";
  eligibilityLabel: string;
};

export type CopilotAnswer = {
  answer: string;
  citations: CopilotCitation[];
  cards: CopilotCard[];
  note: string | null;
};

// Money-Finder: a funding/subsidy program the org may qualify for.
export type ProgramMatch = {
  id: string;
  programId: string | null;
  name: string;
  funder: string | null;
  programType: string | null;
  fitScore: number | null;
  decision: string | null; // apply | review | no_apply
  reasonsFor: string[];
  reasonsAgainst: string[];
  keyFactors: string[];
  benefit: string | null;
  howToApply: string | null;
  citation: string | null;
};

// Filled Forms: a submission form with fields auto-filled from the Company Brain.
export type FilledField = {
  fieldId: string;
  label: string;
  value: string | null;
  status: string; // filled | missing
  source: string; // auto | manual
  note: string;
};

export type FilledForm = {
  formId: string;
  name: string;
  description: string;
  citation: string;
  filledCount: number;
  missingRequired: number;
  fields: FilledField[];
};

// Stay eligible (renewals/obligations): GET /orgs/{orgId}/obligations →
// list of recurring deadlines. PATCH /orgs/{orgId}/obligations/{id} mutates
// status (mark done/undo) and notifyLeadDays (reminder lead window).
// NOTE: the wire response intentionally omits notifyLeadDays, so the reminder
// on/off state cannot be read back from the server (see page for handling).
export type ObligationStatus =
  | "upcoming"
  | "due_soon"
  | "overdue"
  | "completed"
  | "dismissed";

export type Obligation = {
  id: string;
  kind: string;
  title: string;
  description: string | null;
  dueDate: string; // ISO date (YYYY-MM-DD)
  recurrence: string;
  status: ObligationStatus | string;
  source: string;
  lastNotifiedAt: string | null;
};

export type FilingAggregate = {
  filing: FilingResponse;
  opportunity: OpportunitySummary | null;
  requirements: RequirementResponse[];
  requirementCount: number;
  status: string;
  complianceMatrix: ComplianceRow[];
  gapList: ComplianceRow[];
  matchSummary: Record<string, number>;
  recommendation: RecommendationDetail | null;
  approvals: ApprovalItem[];
  generatedDocuments: GeneratedDocSummary[];
  packageReady: boolean;
};
