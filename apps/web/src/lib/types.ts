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
