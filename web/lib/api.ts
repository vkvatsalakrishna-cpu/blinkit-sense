import { API_BASE } from "./constants";
import type {
  ApiErrorBody,
  Household,
  NeedsResponse,
  Product,
  SituationsResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    /* empty */
  }

  const detail = body.detail;
  const message =
    (typeof detail === "object" && detail?.message) ||
    (typeof detail === "string" ? detail : undefined) ||
    body.message ||
    "Something went wrong. Please try again.";

  const code =
    (typeof detail === "object" && detail?.error) || body.error || undefined;

  return new ApiError(res.status, message, code);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    throw await parseError(res);
  }

  return res.json() as Promise<T>;
}

export async function fetchHouseholds(): Promise<Household[]> {
  const data = await apiFetch<{ households: Household[] }>("/households");
  return data.households;
}

export async function fetchCatalogProduct(
  skuId: string,
  location: string,
): Promise<Product | null> {
  const items = await apiFetch<Product[]>(
    `/catalog?sku_id=${encodeURIComponent(skuId)}&location=${encodeURIComponent(location)}`,
  );
  return items[0] ?? null;
}

export async function fetchProductsBySkuIds(
  skuIds: string[],
  location: string,
): Promise<Map<string, Product>> {
  const unique = [...new Set(skuIds)];
  const results = await Promise.all(
    unique.map((id) => fetchCatalogProduct(id, location)),
  );
  const map = new Map<string, Product>();
  unique.forEach((id, i) => {
    const product = results[i];
    if (product) map.set(id, product);
  });
  return map;
}

export async function fetchProductDetails(
  skuId: string,
): Promise<Product | null> {
  const items = await apiFetch<Product[]>(
    `/catalog?sku_id=${encodeURIComponent(skuId)}`,
  );
  return items[0] ?? null;
}

export async function postSituations(body: {
  household_id: string;
  cart: { sku_id: string; qty: number }[];
  location: string;
  today: string;
}): Promise<SituationsResponse> {
  return apiFetch<SituationsResponse>("/situations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function postNeeds(body: {
  household_id: string;
  situation_id: string;
  cart: { sku_id: string; qty: number }[];
  location: string;
  situation_label?: string;
  prompt_context?: string;
}): Promise<NeedsResponse> {
  return apiFetch<NeedsResponse>("/needs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      return err.message;
    }
    return err.message;
  }
  if (err instanceof TypeError) {
    return "Could not reach the server. Is the API running on port 8000?";
  }
  return "Something went wrong. Please try again.";
}
