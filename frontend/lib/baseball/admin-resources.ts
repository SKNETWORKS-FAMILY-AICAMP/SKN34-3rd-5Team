import type { AdminResourceName } from "./wire";

export type AdminResource = { name: AdminResourceName; label: string; group: string; fields: string[] };
const definitions: [string, string, string, string][] = [
  ["teams", "구단", "구단·구장", "id team_code team_name_ko"],
  ["stadiums", "구장", "구단·구장", "id stadium_code stadium_name_ko address longitude latitude geocode_source facility_manager game_operator phone_general phone_facility phone_ticket collected_at"],
  ["home-contexts", "홈구장 맥락", "구단·구장", "id season team_id stadium_id"],
  ["postseason-stages", "포스트시즌 단계", "경기·순위", "id stage_code stage_name start_date end_date matchup_description status_tag collected_at"],
  ["games", "경기", "경기·순위", "id game_code home_team_id away_team_id stadium_id postseason_stage_id game_date game_time home_score away_score status_code game_type collected_at"],
  ["standing-histories", "순위 스냅샷", "경기·순위", "id team_id snapshot_date rank wins losses draws games_behind collected_at"],
  ["seat-zones", "좌석 구역", "좌석·티켓", "id home_context_id zone_code zone_name_ko level side seat_type group_size accessible"],
  ["ticket-prices", "티켓 가격", "좌석·티켓", "id seat_zone_id price_tier day_type customer_type group_size price_krw valid_from valid_to discount_condition collected_at"],
  ["ticket-policies", "예매 정책", "좌석·티켓", "id policy_code team_id game_id policy_type subtype open_at max_tickets channel_no booking_channel channel_condition collected_at"],
  ["seat-maps", "좌석도", "좌석·티켓", "id home_context_id map_title page_url"],
  ["seat-map-assets", "좌석도 이미지", "좌석·티켓", "id seat_map_id asset_no asset_url asset_role"],
  ["seat-scopes", "시야 범위", "좌석·티켓", "id home_context_id scope_code scope_name"],
  ["seat-views", "좌석 시야", "좌석·티켓", "id seat_scope_id view_characteristic roof_coverage evidence_scope"],
  ["food-stores", "공식 매점", "매장·먹거리", "id record_code stadium_id store_facility location_qty collected_at"],
  ["food-store-locations", "매점 위치", "매장·먹거리", "id food_store_id location_no floor zone_location"],
  ["food-store-menus", "메뉴 분류", "매장·먹거리", "id food_store_id menu_category_official"],
  ["transports", "교통·주차", "교통·시설", "id stadium_id access_code mode title details parking_spaces reservation_required collected_at"],
  ["stadium-contents", "부가 콘텐츠", "교통·시설", "id record_code stadium_id content_type name floor location official_description operating_condition collected_at"],
  ["facilities", "편의시설", "교통·시설", "id record_code stadium_id facility_type floor side nearby_section gate gender indoor_outdoor location_detail collected_at"],
];
export const adminResources: AdminResource[] = definitions.map(([name, label, group, fields]) => ({ name: name as AdminResourceName, label, group, fields: fields.split(" ") }));
export const adminResourceNames = new Set(adminResources.map(item => item.name));
export const relationResources: Record<string, AdminResourceName> = { team_id: "teams", home_team_id: "teams", away_team_id: "teams", stadium_id: "stadiums", postseason_stage_id: "postseason-stages", home_context_id: "home-contexts", seat_zone_id: "seat-zones", game_id: "games", seat_map_id: "seat-maps", seat_scope_id: "seat-scopes", food_store_id: "food-stores" };
export const booleanFields = new Set(["accessible", "reservation_required"]);
export const nullableFields = new Set(["facility_manager", "game_operator", "phone_general", "phone_facility", "phone_ticket", "home_team_id", "away_team_id", "stadium_id", "postseason_stage_id", "game_id", "home_score", "away_score", "group_size", "valid_from", "valid_to", "open_at", "max_tickets", "parking_spaces", "accessible", "reservation_required", "location_qty"]);
export const numericFields = new Set(adminResources.flatMap(item => item.fields.filter(field => field === "id" || field.endsWith("_id") || /^(season|rank|wins|losses|draws|.*score|.*size|.*qty|.*no|price_krw|max_tickets|parking_spaces|longitude|latitude)$/.test(field))));

export function relationIds(values: unknown[]) {
  return values.flatMap(value => {
    const id = typeof value === "number" ? value : typeof value === "string" && value.trim() ? Number(value) : NaN;
    return Number.isSafeInteger(id) && id > 0 ? [id] : [];
  });
}

export function formValue(field: string, value: unknown) {
  if (value === null || value === undefined) return "";
  if (!field.endsWith("_at") || typeof value !== "string") return String(value);
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  return new Date(instant.getTime() - instant.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function mutationValues(fields: string[], values: Record<string, unknown>, original?: Record<string, unknown>) {
  const result: Record<string, unknown> = {};
  for (const field of fields) {
    if (original && (field === "id" || values[field] === original[field])) continue;
    const value = formValue(field, values[field]);
    if (nullableFields.has(field) && value === "") result[field] = null;
    else if (booleanFields.has(field)) result[field] = value === "true" ? true : value === "false" ? false : null;
    else if (numericFields.has(field) && value !== "") result[field] = Number(value);
    if (field.endsWith("_at") && value) {
      const instant = new Date(value);
      result[field] = Number.isNaN(instant.getTime()) ? value : instant.toISOString();
    }
    else if (!(field in result)) result[field] = value;
  }
  return result;
}
