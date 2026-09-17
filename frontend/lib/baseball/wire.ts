import type { components } from "../api/schema";

type Schemas = components["schemas"];

export type AdminResourceDtoMap = {
  teams: Schemas["Team"];
  stadiums: Schemas["Stadium"];
  "home-contexts": Schemas["HomeContext"];
  "postseason-stages": Schemas["PostseasonStage"];
  games: Schemas["Game"];
  "standing-histories": Schemas["StandingHistory"];
  "seat-zones": Schemas["SeatZone"];
  "ticket-prices": Schemas["TicketPrice"];
  "ticket-policies": Schemas["TicketPolicy"];
  "seat-maps": Schemas["SeatMap"];
  "seat-map-assets": Schemas["SeatMapAsset"];
  "seat-scopes": Schemas["SeatScope"];
  "seat-views": Schemas["SeatView"];
  "food-stores": Schemas["FoodStore"];
  "food-store-locations": Schemas["FoodStoreLocation"];
  "food-store-menus": Schemas["FoodStoreMenu"];
  transports: Schemas["Transport"];
  "stadium-contents": Schemas["StadiumContent"];
  facilities: Schemas["Facility"];
};

export type AdminDetailDtoMap = {
  teams: Schemas["TeamDetail"];
  stadiums: Schemas["StadiumDetail"];
  "home-contexts": Schemas["HomeContextDetail"];
  "postseason-stages": Schemas["PostseasonStageDetail"];
  games: Schemas["GameDetail"];
  "standing-histories": Schemas["StandingHistoryDetail"];
  "seat-zones": Schemas["SeatZoneDetail"];
  "ticket-prices": Schemas["TicketPriceDetail"];
  "ticket-policies": Schemas["TicketPolicyDetail"];
  "seat-maps": Schemas["SeatMapDetail"];
  "seat-map-assets": Schemas["SeatMapAssetDetail"];
  "seat-scopes": Schemas["SeatScopeDetail"];
  "seat-views": Schemas["SeatViewDetail"];
  "food-stores": Schemas["FoodStoreDetail"];
  "food-store-locations": Schemas["FoodStoreLocationDetail"];
  "food-store-menus": Schemas["FoodStoreMenuDetail"];
  transports: Schemas["TransportDetail"];
  "stadium-contents": Schemas["StadiumContentDetail"];
  facilities: Schemas["FacilityDetail"];
};

export type AdminResourceName = keyof AdminResourceDtoMap;
export type AdminRowDto = AdminResourceDtoMap[AdminResourceName];
export type AdminDetailRowDto = AdminDetailDtoMap[AdminResourceName];

export type PublicStadiumDto = Schemas["PublicStadium"];
export type SeatZoneDto = Schemas["SeatZone"];
export type TicketPriceDto = Schemas["PublicTicketPrice"];
export type TicketPolicyDto = Schemas["TicketPolicy"];
export type SeatMapDto = Schemas["PublicSeatMap"];
export type SeatViewDto = Schemas["SeatView"];
export type FoodStoreDto = Schemas["PublicFoodStore"];
export type TransportDto = Schemas["Transport"];
export type FacilityDto = Schemas["Facility"];
export type StadiumContentDto = Schemas["StadiumContent"];
