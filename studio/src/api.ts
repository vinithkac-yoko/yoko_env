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

export interface TreeNode {
  id: string;
  name: string;
  area: string;
  garment_type: string;
  tags: string[];
  children: TreeNode[];
}

export const fetchFamilyTree = (token: string) =>
  getJson<{ roots: TreeNode[] }>("/api/library/tree", token).then((r) => r.roots);

/** The tree flattened for display: each pattern with how deep it sits under the basic set. */
export function flattenTree(roots: TreeNode[]): { node: TreeNode; depth: number }[] {
  const out: { node: TreeNode; depth: number }[] = [];
  const walk = (nodes: TreeNode[], depth: number) => {
    for (const node of nodes) {
      out.push({ node, depth });
      walk(node.children, depth + 1);
    }
  };
  walk(roots, 0);
  return out;
}

// -- the studio (stage A) ----------------------------------------------------------------------

/** An API error, with the server's own words (FastAPI's `detail`). */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let message = `${res.status}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "some fields are not right";
    } catch {
      /* not JSON: keep the status */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export interface Person {
  id: number;
  email: string;
  name: string;
  role: "owner" | "maker";
  disabled?: boolean;
}

export interface AuthStatus {
  database: boolean;
  database_problem: string;
  session_secret: boolean;
  owner_exists: boolean;
}

export const authStatus = () => call<AuthStatus>("GET", "/api/auth/status");
export const me = () => call<{ user: Person }>("GET", "/api/auth/me").then((r) => r.user);
export const setup = (b: { token: string; email: string; name: string; password: string }) =>
  call<{ user: Person }>("POST", "/api/auth/setup", b).then((r) => r.user);
export const login = (email: string, password: string) =>
  call<{ user: Person }>("POST", "/api/auth/login", { email, password }).then((r) => r.user);
export const logout = () => call<{ ok: boolean }>("POST", "/api/auth/logout");
export const changePassword = (old_password: string, new_password: string) =>
  call<{ ok: boolean }>("POST", "/api/auth/password", { old_password, new_password });

export const listPeople = () => call<{ people: Person[] }>("GET", "/api/people").then((r) => r.people);
export const addPerson = (b: { email: string; name: string; password: string }) =>
  call<{ id: number }>("POST", "/api/people", b);
export const resetPassword = (id: number, password: string) =>
  call<{ ok: boolean }>("POST", `/api/people/${id}/password`, { password });
export const setDisabled = (id: number, disabled: boolean) =>
  call<{ ok: boolean }>("POST", `/api/people/${id}/disabled`, { disabled });

export interface MeasurementFile {
  id: number;
  name: string;
  unit: string;
  by: string;
  created_at: string;
}

export const listMeasurements = () =>
  call<{ files: MeasurementFile[] }>("GET", "/api/measurements").then((r) => r.files);
export const addMeasurements = (name: string, content: string) =>
  call<{ id: number; measurements: number }>("POST", "/api/measurements", { name, content });

export interface StartPattern {
  id: string;
  name: string;
  area: string;
  locked: boolean;
  pieces: string[];
}

export interface SizeChoice {
  key: string;
  label: string;
}

export const listPatterns = () =>
  call<{ patterns: StartPattern[] }>("GET", "/api/patterns").then((r) => r.patterns);
export const patternSizes = (id: string) =>
  call<{ sizes: SizeChoice[]; default: string }>("GET", `/api/patterns/${id}/sizes`);
export const listRecipes = () =>
  call<{ recipes: string[] }>("GET", "/api/recipes").then((r) => r.recipes);

export type ItemMeasurements =
  | { kind: "table"; size?: number | null; height?: number | null }
  | { kind: "person"; id: number };

export interface Item {
  id: number;
  kind: "recipe_example" | "design";
  recipe: string | null;
  example_no: number | null;
  title: string;
  brief: string;
  start_pattern: string;
  pieces: string[];
  measurements: ItemMeasurements;
  author_id: number;
  author: string;
  status: "open" | "finished";
  created_at: string;
  finished_at: string | null;
  can_edit: boolean;
}

export interface NewItem {
  kind: Item["kind"];
  recipe?: string | null;
  example_no?: number | null;
  title: string;
  brief?: string;
  start_pattern: string;
  pieces: string[];
  measurements: ItemMeasurements;
}

export const listItems = () => call<{ items: Item[]; hidden: number }>("GET", "/api/items");
export const createItem = (b: NewItem) => call<{ id: number }>("POST", "/api/items", b);
export const getItem = (id: number) => call<{ item: Item }>("GET", `/api/items/${id}`).then((r) => r.item);
export const finishItem = (id: number) => call<{ ok: boolean }>("POST", `/api/items/${id}/finish`);
export const reopenItem = (id: number) => call<{ ok: boolean }>("POST", `/api/items/${id}/reopen`);
export const itemSizes = (id: number) =>
  call<{ sizes: SizeChoice[]; default: string }>("GET", `/api/items/${id}/sizes`);

export type Pt = [number, number];

export interface Scene {
  lines: { id: number; a: Pt; b: Pt }[];
  curves: { id: number; name: string; points: Pt[] }[];
  points: { id: number; label: string; x: number; y: number }[];
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number };
  focus: { min_x: number; min_y: number; max_x: number; max_y: number } | null;
  proposed_landmarks: Record<string, string[]>;
  errors: { code: string; message: string; object_id: number | null }[];
  size: SizeChoice;
  pieces: string[];
}

export const itemScene = (id: number, size?: string) =>
  call<Scene>("GET", `/api/items/${id}/scene${size ? `?size=${encodeURIComponent(size)}` : ""}`);

export interface ObjectInfo {
  id: number;
  name: string;
  kind: string;
  tool?: string;
  attributes?: Record<string, string>;
  built_from: (string | null)[];
  used_by: (string | null)[];
  history: { what: string; step: string | null }[];
  x_mm?: number;
  y_mm?: number;
  length?: number;
  unit?: string;
  edit_with?: string;
  delete_with?: string;
  proposed_landmarks: string[];
  built_from_ids: ObjectRef[];
  used_by_ids: ObjectRef[];
}

export const itemObject = (id: number, objectId: number, size?: string) =>
  call<{ object: ObjectInfo }>(
    "GET",
    `/api/items/${id}/objects/${objectId}${size ? `?size=${encodeURIComponent(size)}` : ""}`,
  ).then((r) => r.object);

export interface ObjectRef {
  id: number;
  name: string;
}
