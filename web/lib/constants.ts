import type { ScenarioPreset } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const FEE_DELIVERY = 30;
export const FEE_HANDLING = 12;
export const FEE_SMALL_CART = 20;
export const CART_THRESHOLD = 99;

export const BASE_CONFIDENCE_THRESHOLD = 0.4;
export const MIN_CONFIDENCE_THRESHOLD = 0.25;
export const THRESHOLD_REFERENCE_ORDERS = 12;

export function confidenceThreshold(ordersPerMonth: number): number {
  const adjusted =
    BASE_CONFIDENCE_THRESHOLD -
    Math.max(0, THRESHOLD_REFERENCE_ORDERS - ordersPerMonth) * 0.02;
  return Math.max(MIN_CONFIDENCE_THRESHOLD, adjusted);
}

export function feeBreakdown(subtotal: number) {
  const smallCart = subtotal < CART_THRESHOLD ? FEE_SMALL_CART : 0;
  return {
    delivery: FEE_DELIVERY,
    handling: FEE_HANDLING,
    smallCart,
    totalFees: FEE_DELIVERY + FEE_HANDLING + smallCart,
    gapToThreshold: Math.max(0, CART_THRESHOLD - subtotal),
  };
}

/** Preset demo carts — SKU ids resolved via GET /catalog?sku_id= */
export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "festival_gifting",
    label: "Festival Gifting",
    householdId: "h1",
    skuIds: ["sku_021", "sku_022", "sku_023"],
  },
  {
    id: "moving_in",
    label: "Moving In",
    householdId: "h2",
    skuIds: ["sku_022", "sku_025"],
  },
  {
    id: "stocking",
    label: "Stocking Up",
    householdId: "h4",
    skuIds: ["sku_022", "sku_025", "sku_026"],
  },
  {
    id: "cooking_project",
    label: "Cooking",
    householdId: "h1",
    skuIds: ["sku_041", "sku_042"],
  },
  {
    id: "new_pet",
    label: "New Pet",
    householdId: "h3",
    skuIds: ["sku_020"],
  },
];

export function catalogLocationFromAddress(address: string): string {
  if (address.includes("Delhi")) return "Delhi NCR";
  if (address.toLowerCase().includes("whitefield")) return "Whitefield";
  return "Sarjapur";
}
