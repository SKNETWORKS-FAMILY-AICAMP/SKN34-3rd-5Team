import { stadiums } from "@/lib/stadiums";

export const runtime = "nodejs";
type Item = { category: string; fcstDate: string; fcstTime: string; fcstValue: string };
const cache = new Map<string, { expires: number; value: Promise<Item[]> }>();
// KMA's Lambert conformal conic projection, 5 km forecast grid.
function grid(lat: number, lng: number) {
  const rad = Math.PI / 180, re = 6371.00877 / 5;
  const sn = Math.log(Math.cos(30 * rad) / Math.cos(60 * rad)) / Math.log(Math.tan(Math.PI / 4 + 60 * rad / 2) / Math.tan(Math.PI / 4 + 30 * rad / 2));
  const sf = Math.pow(Math.tan(Math.PI / 4 + 30 * rad / 2), sn) * Math.cos(30 * rad) / sn;
  const ro = re * sf / Math.pow(Math.tan(Math.PI / 4 + 38 * rad / 2), sn);
  const ra = re * sf / Math.pow(Math.tan(Math.PI / 4 + lat * rad / 2), sn), theta = (lng - 126) * rad * sn;
  return { nx: Math.floor(ra * Math.sin(theta) + 43.5), ny: Math.floor(ro - ra * Math.cos(theta) + 136.5) };
}
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const code = params.get("stadium"), date = params.get("date") ?? "", time = params.get("time") ?? "";
  const stadium = stadiums.find(item => item.code === code);
  const unavailable = () => Response.json({ weather: null }, { headers: { "Cache-Control": "no-store" } });
  if (!stadium || !/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return unavailable();
  const target = new Date(`${date}T${time}:00+09:00`).getTime();
  if (!Number.isFinite(target) || target < Date.now() - 86400000 || target > Date.now() + 5 * 86400000) return unavailable();
  const rawKey = (process.env.KMA_SERVICE_KEY ?? process.env.KMA_API_KEY)?.trim();
  if (!rawKey) return unavailable();
  let key = rawKey;
  try { key = decodeURIComponent(rawKey); } catch { return unavailable(); }
  // Allow an hour for publication; use a forecast issued before the game.
  const base = new Date(Math.min(Date.now(), target) - 3600000 + 9 * 3600000);
  const hours = [2, 5, 8, 11, 14, 17, 20, 23];
  let hour = hours.filter(value => value <= base.getUTCHours()).at(-1);
  if (hour === undefined) { base.setUTCDate(base.getUTCDate() - 1); hour = 23; }
  const baseDate = base.toISOString().slice(0, 10).replaceAll("-", ""), baseTime = `${String(hour).padStart(2, "0")}00`;
  const { nx, ny } = grid(stadium.lat, stadium.lng);
  const cacheKey = `${baseDate}:${baseTime}:${nx}:${ny}`;
  try {
    let entry = cache.get(cacheKey);
    if (!entry || entry.expires < Date.now()) {
      for (const [id, item] of cache) if (item.expires < Date.now()) cache.delete(id);
      const value = (async () => {
        const url = new URL("https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst");
        url.search = new URLSearchParams({ serviceKey: key, pageNo: "1", numOfRows: "2000", dataType: "JSON", base_date: baseDate, base_time: baseTime, nx: String(nx), ny: String(ny) }).toString();
        const response = await fetch(url, { signal: AbortSignal.timeout(12000), cache: "no-store" });
        if (!response.ok) throw new Error("Weather unavailable");
        const body = await response.json();
        if (body.response?.header?.resultCode !== "00" || !Array.isArray(body.response?.body?.items?.item)) throw new Error("Weather unavailable");
        return body.response.body.items.item as Item[];
      })();
      entry = { expires: Date.now() + 600000, value }; cache.set(cacheKey, entry);
    }
    const items = await entry.value;
    const rounded = new Date(Math.round(target / 3600000) * 3600000 + 9 * 3600000).toISOString();
    const forecastDate = rounded.slice(0, 10).replaceAll("-", ""), forecastTime = rounded.slice(11, 13) + "00";
    const values = Object.fromEntries(items.filter(item => item.fcstDate === forecastDate && item.fcstTime === forecastTime).map(item => [item.category, item.fcstValue]));
    const temperature = Number(values.TMP);
    const sky = ({ "1": "맑음", "3": "구름많음", "4": "흐림" } as Record<string, string>)[values.SKY];
    const rain = ({ "1": "비", "2": "비/눈", "3": "눈", "4": "소나기" } as Record<string, string>)[values.PTY];
    if (!values.TMP?.trim() || !Number.isFinite(temperature) || !(rain ?? sky)) return unavailable();
    return Response.json({ weather: { label: rain ?? sky, temperature, forecastDate, forecastTime, issuedAt: `${baseDate} ${baseTime}`, source: "기상청" } });
  } catch { return unavailable(); }
}
