import assert from "node:assert/strict";
import test from "node:test";
import { adminResources, formValue, mutationValues, relationIds } from "../lib/baseball/admin-resources.ts";

test("admin resources keep the approved five groups and 19 models", () => {
  assert.equal(adminResources.length, 19);
  assert.equal(new Set(adminResources.map(resource => resource.group)).size, 5);
});

test("an untouched collected_at is omitted so its exact instant survives PATCH", () => {
  const original = { id: 7, collected_at: "2026-09-14T11:22:33.456789Z" };
  assert.equal(formValue("collected_at", original.collected_at).length, 16);
  assert.deepEqual(mutationValues(["id", "collected_at"], { ...original }, original), {});
});

test("edited datetime-local and optional values use API-native types", () => {
  const result = mutationValues(
    ["collected_at", "home_score", "location_qty", "accessible", "facility_manager", "price_krw"],
    { collected_at: "2026-09-14T20:30", home_score: "", location_qty: "12", accessible: "false", facility_manager: "", price_krw: "25000" },
  );
  assert.equal(result.collected_at, new Date("2026-09-14T20:30").toISOString());
  assert.deepEqual(result, { collected_at: result.collected_at, home_score: null, location_qty: 12, accessible: false, facility_manager: null, price_krw: 25000 });
});

test("relation fetch IDs reject empty and invalid values while retaining valid selections", () => {
  assert.deepEqual(relationIds([null, undefined, "", "  ", 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, "7", 8]), [7, 8]);
});
