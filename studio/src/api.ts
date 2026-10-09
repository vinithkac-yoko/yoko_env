export interface Health {
  status: string;
  version: string;
}

export interface BuildInfo {
  git_sha: string;
  phase: number;
  seamly2d_pin: string;
  pattern_formats_read: string[];
  bundle_versions: Record<string, string>;
  fixtures_hash: string | null;
}

export interface FixtureFile {
  path: string;
  sha256: string;
  area: string;
}

export const shortSha = (sha: string): string => sha.slice(0, 7);

async function getJson<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return (await res.json()) as T;
}

export const fetchHealth = () => getJson<Health>("/api/health");
export const fetchBuild = () => getJson<BuildInfo>("/api/build");
export const fetchFixtures = (token: string) =>
  getJson<{ files: FixtureFile[] }>("/api/fixtures", token).then((r) => r.files);

export interface BaseSummary {
  name: string;
  locked: boolean;
  format: string;
  unit: string;
  objects: number;
  points: number;
  curves: number;
  variables: number;
  issues: number;
  state_hash: string;
  size: number;
  height: number;
}

export const fetchBaseSummary = (token: string) => getJson<BaseSummary>("/api/library/base", token);

export async function fetchBaseSvg(token: string): Promise<string> {
  const res = await fetch("/api/library/base/render.svg", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`render: ${res.status}`);
  return res.text();
}
