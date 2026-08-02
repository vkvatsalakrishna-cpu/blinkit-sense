export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  price: number;
  mrp: number;
  unit: string;
  available_in: string[];
  image_url?: string;
  blinkit_product_id?: string;
  popularity_rank?: number | null;
}

export type CategoryBrowseFilter = "budget" | "premium" | "popular";

export interface CartLine {
  sku_id: string;
  qty: number;
  product: Product;
}

export interface Household {
  id: string;
  name: string;
  known_addresses: string[];
  current_address: string;
  orders_per_month: number;
  order_history: { sku: string; orders_per_month: number }[];
  current_cart: string[];
}

export interface SituationCandidate {
  id: string;
  label: string;
  reasoning: string;
  score: number;
}

export interface SituationsResponse {
  confidence: number;
  candidates: SituationCandidate[];
}

export interface SuggestionOption {
  resolved_sku: string;
  resolved_name: string;
  price: number;
  category: string;
  image_url?: string;
}

export interface SuggestionItem {
  role: string;
  need: string;
  why?: string;
  quantity_reasoning?: string;
  resolved_sku: string;
  resolved_name: string;
  price: number;
  category: string;
  flag?: "new_category" | "deepening";
  options?: SuggestionOption[];
  option_index?: number;
}

export interface NeedsResponse {
  situation_label: string;
  items: SuggestionItem[];
  reserve?: SuggestionItem[];
  gaps: unknown[];
  sensitive_guidance: string[];
  unavailable?: string[];
  cart_subtotal: number;
  suggested_total: number;
  fee: {
    delivery: number;
    handling: number;
    small_cart: number;
    total_fees: number;
    gap_to_threshold: number;
  };
}

export interface ApiErrorBody {
  error?: string;
  message?: string;
  detail?: { error?: string; message?: string } | string;
}

export type FlowPhase =
  | "cart"
  | "situations_loading"
  | "situations"
  | "needs_loading"
  | "suggestions"
  | "dismissed"
  | "order_confirmed";

export interface ScenarioPreset {
  id: string;
  label: string;
  householdId: string;
  skuIds: string[];
}

export interface SelectedSuggestion {
  item: SuggestionItem;
  product: Product | null;
  qty: number;
  checked: boolean;
  dismissed: boolean;
  optionIndex: number;
}
