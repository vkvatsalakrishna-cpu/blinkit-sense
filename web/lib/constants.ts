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

/** Preset demo carts — mixed-category inference carts; all SKUs have image_url in Sarjapur */
export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "scenario_1",
    label: "Scenario 1",
    householdId: "h4",
    skuIds: ["sku_6155", "sku_4850", "sku_1652", "sku_476"],
  },
  {
    id: "scenario_2",
    label: "Scenario 2",
    householdId: "h3",
    skuIds: ["sku_2826", "sku_1876", "sku_1222"],
  },
  {
    id: "scenario_3",
    label: "Scenario 3",
    householdId: "h1",
    skuIds: ["sku_253", "sku_263", "sku_1024", "sku_2210"],
  },
  {
    id: "scenario_4",
    label: "Scenario 4",
    householdId: "h4",
    skuIds: ["sku_275", "sku_590", "sku_1324"],
  },
  {
    id: "scenario_5",
    label: "Scenario 5",
    householdId: "h2",
    skuIds: ["sku_2213", "sku_1236", "sku_353", "sku_2007"],
  },
  {
    id: "scenario_6",
    label: "Scenario 6",
    householdId: "h1",
    skuIds: ["sku_582", "sku_607", "sku_4682", "sku_3917"],
  },
  {
    id: "scenario_7",
    label: "Scenario 7",
    householdId: "h3",
    skuIds: ["sku_2662", "sku_3173", "sku_4723"],
  },
  {
    id: "scenario_8",
    label: "Scenario 8",
    householdId: "h1",
    skuIds: ["sku_263", "sku_738", "sku_3708", "sku_4503"],
  },
];

export function catalogLocationFromAddress(address: string): string {
  if (address.includes("Delhi")) return "Delhi NCR";
  if (address.toLowerCase().includes("whitefield")) return "Whitefield";
  return "Sarjapur";
}
