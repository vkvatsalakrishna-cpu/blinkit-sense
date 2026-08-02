import type { ScenarioPreset } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Delivery addresses shown in the header — one option per catalog area */
export const DELIVERY_LOCATIONS = [
  "Sarjapur, Bangalore",
  "HSR Layout, Bangalore",
] as const;

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

/** Preset demo carts — heterogeneous cross-category mixes; all SKUs verified in Sarjapur catalog with image_url */
export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "scenario_1",
    label: "Scenario 1",
    householdId: "h1",
    skuIds: ["sku_3308", "sku_4878", "sku_22717", "sku_24301"],
  },
  {
    id: "scenario_2",
    label: "Scenario 2",
    householdId: "h2",
    skuIds: ["sku_7488", "sku_15192", "sku_17135", "sku_11541"],
  },
  {
    id: "scenario_3",
    label: "Scenario 3",
    householdId: "h3",
    skuIds: ["sku_21297", "sku_22341", "sku_10380", "sku_3708"],
  },
  {
    id: "scenario_4",
    label: "Scenario 4",
    householdId: "h4",
    skuIds: ["sku_13951", "sku_13980", "sku_14202", "sku_18548"],
  },
  {
    id: "scenario_5",
    label: "Scenario 5",
    householdId: "h1",
    skuIds: ["sku_2826", "sku_1876", "sku_12243"],
  },
  {
    id: "scenario_6",
    label: "Scenario 6",
    householdId: "h2",
    skuIds: ["sku_20901", "sku_9712", "sku_20910", "sku_3889", "sku_4719"],
  },
  {
    id: "scenario_7",
    label: "Scenario 7",
    householdId: "h3",
    skuIds: ["sku_253", "sku_263", "sku_1062", "sku_2210"],
  },
  {
    id: "scenario_8",
    label: "Scenario 8",
    householdId: "h4",
    skuIds: ["sku_18488", "sku_10572", "sku_4682"],
  },
  {
    id: "scenario_9",
    label: "Scenario 9",
    householdId: "h1",
    skuIds: ["sku_22656", "sku_12245", "sku_25638", "sku_24707"],
  },
  {
    id: "scenario_10",
    label: "Scenario 10",
    householdId: "h2",
    skuIds: ["sku_11702", "sku_12100", "sku_2087", "sku_28965"],
  },
  {
    id: "scenario_11",
    label: "Scenario 11",
    householdId: "h3",
    skuIds: ["sku_24002", "sku_17330", "sku_1324", "sku_22546"],
  },
  {
    id: "scenario_12",
    label: "Scenario 12",
    householdId: "h4",
    skuIds: ["sku_19781", "sku_3308", "sku_19236", "sku_23564"],
  },
];

export function catalogLocationFromAddress(address: string): string {
  if (address.includes("Delhi")) return "Delhi NCR";
  if (address.toLowerCase().includes("whitefield")) return "Whitefield";
  return "Sarjapur";
}
