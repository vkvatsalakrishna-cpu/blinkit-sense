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

/** Preset demo carts — heterogeneous cross-category mixes; all SKUs verified in Sarjapur catalog with image_url */
export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: "scenario_1",
    label: "Scenario 1",
    householdId: "h1",
    skuIds: ["sku_6255", "sku_4878", "sku_22717", "sku_24301"],
  },
  {
    id: "scenario_2",
    label: "Scenario 2",
    householdId: "h2",
    skuIds: ["sku_7488", "sku_15040", "sku_17317"],
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
    skuIds: ["sku_14624", "sku_14139", "sku_14384", "sku_11701"],
  },
  {
    id: "scenario_5",
    label: "Scenario 5",
    householdId: "h1",
    skuIds: ["sku_2826", "sku_1876", "sku_12425"],
  },
  {
    id: "scenario_6",
    label: "Scenario 6",
    householdId: "h2",
    skuIds: ["sku_21083", "sku_9923", "sku_20347", "sku_3889"],
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
    skuIds: ["sku_17565", "sku_10453", "sku_12457"],
  },
  {
    id: "scenario_9",
    label: "Scenario 9",
    householdId: "h1",
    skuIds: ["sku_22758", "sku_25952", "sku_12427", "sku_24066"],
  },
  {
    id: "scenario_10",
    label: "Scenario 10",
    householdId: "h2",
    skuIds: ["sku_11702", "sku_12282", "sku_25165", "sku_13877"],
  },
  {
    id: "scenario_11",
    label: "Scenario 11",
    householdId: "h3",
    skuIds: ["sku_17990", "sku_17519", "sku_1324"],
  },
  {
    id: "scenario_12",
    label: "Scenario 12",
    householdId: "h4",
    skuIds: ["sku_19962", "sku_5394", "sku_19418", "sku_23834"],
  },
];

export function catalogLocationFromAddress(address: string): string {
  if (address.includes("Delhi")) return "Delhi NCR";
  if (address.toLowerCase().includes("whitefield")) return "Whitefield";
  return "Sarjapur";
}
