"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { adminResources, booleanFields, formValue, mutationValues, nullableFields, numericFields, relationIds, relationResources } from "@/lib/baseball/admin-resources";
import { createAdminRow, deleteAdminRow, fetchAdminDetail, fetchAdminPage, updateAdminRow } from "@/lib/baseball/client";
import type { AdminDetailRowDto, AdminResourceName, AdminRowDto } from "@/lib/baseball/wire";
import styles from "./page.module.css";

type Row = AdminRowDto | AdminDetailRowDto;
type LoadedPage = { count: number; results: AdminRowDto[]; resource: AdminResourceName };
type RelationPage = { count: number; results: AdminRowDto[]; page: number; query: string };

const groups = [...new Set(adminResources.map(item => item.group))];
const inputType = (field: string) => field.endsWith("_at") ? "datetime-local" : field.includes("date") || field === "valid_from" || field === "valid_to" ? "date" : field === "game_time" ? "time" : numericFields.has(field) ? "number" : "text";
const labels: Record<string, string> = { id: "ID", team_code: "구단 코드", team_name_ko: "구단명", stadium_code: "구장 코드", stadium_name_ko: "구장명", address: "주소", collected_at: "수집 시각", season: "시즌", game_date: "경기일", game_time: "경기 시각", price_krw: "가격(원)", discount_condition: "할인 조건", location_detail: "상세 위치", menu_category_official: "공식 메뉴 분류", official_description: "공식 설명", indoor_outdoor: "실내·외" };
const words: Record<string, string> = { home: "홈", away: "원정", team: "구단", stadium: "구장", postseason: "포스트시즌", stage: "단계", seat: "좌석", zone: "구역", map: "지도", asset: "이미지", scope: "범위", food: "매점", store: "매장", game: "경기", code: "코드", name: "이름", ko: "한국어", source: "출처", manager: "관리기관", operator: "운영기관", phone: "전화", general: "대표", facility: "시설", ticket: "티켓", date: "날짜", time: "시각", score: "점수", status: "상태", type: "유형", rank: "순위", wins: "승", losses: "패", draws: "무", games: "경기", behind: "게임차", level: "층", side: "방향", group: "인원", size: "수", qty: "수", accessible: "접근성", price: "가격", tier: "등급", day: "요일", customer: "대상", valid: "유효", from: "시작", to: "종료", policy: "정책", subtype: "세부 유형", open: "오픈", max: "최대", channel: "채널", booking: "예매", condition: "조건", title: "제목", url: "URL", no: "번호", role: "역할", view: "시야", characteristic: "특징", roof: "지붕", coverage: "범위", evidence: "근거", record: "레코드", location: "위치", menu: "메뉴", category: "분류", official: "공식", access: "접근", mode: "수단", details: "상세", parking: "주차", spaces: "면수", reservation: "예약", required: "필요", content: "콘텐츠", floor: "층", nearby: "인근", section: "구역", gate: "게이트", gender: "성별", indoor: "실내", outdoor: "실외", longitude: "경도", latitude: "위도", geocode: "지오코딩", description: "설명", operating: "운영", krw: "원", at: "시각" };
const fieldLabel = (field: string) => labels[field] ?? field.split("_").map(word => words[word] ?? word).join(" ");
const wireValue = (row: Row, field: string): unknown => (row as unknown as Record<string, unknown>)[field];
const relationLabel = (row: Row) => String(["team_name_ko", "stadium_name_ko", "record_code", "game_code", "stage_name", "zone_name_ko", "map_title", "scope_name", "name"].map(field => wireValue(row, field)).find(Boolean) ?? row.id);

export default function BaseballAdminPage() {
  const [group, setGroup] = useState(groups[0]);
  const choices = adminResources.filter(item => item.group === group);
  const [resourceName, setResourceName] = useState(choices[0].name);
  const resource = adminResources.find(item => item.name === resourceName) ?? adminResources[0];
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<LoadedPage | null>(null);
  const [editing, setEditing] = useState<Row | null | undefined>(undefined);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [relations, setRelations] = useState<Record<string, RelationPage>>({});
  const [relationQuery, setRelationQuery] = useState<Record<string, string>>({});
  const [relationBusy, setRelationBusy] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const formGeneration = useRef(0);
  const relationGeneration = useRef<Record<string, number>>({});

  useEffect(() => {
    const controller = new AbortController();
    fetchAdminPage(resourceName, page, 30, query, controller.signal)
      .then(body => setData({ count: body.count, results: body.results, resource: resourceName }))
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "목록을 불러오지 못했어요."); });
    return () => controller.abort();
  }, [resourceName, page, query, reload]);

  const relationFields = useMemo(() => resource.fields.filter(field => relationResources[field]), [resource]);

  function selectResource(name: AdminResourceName) {
    formGeneration.current += 1;
    relationGeneration.current = {};
    setResourceName(name); setPage(1); setQuery(""); setData(null); setReload(item => item + 1); setEditing(undefined); setValues({}); setRelations({}); setRelationQuery({}); setFieldErrors({}); setError(""); setNotice(""); setBusy(false); setRelationBusy("");
  }

  async function relationPage(name: AdminResourceName, targetPage: number, search: string, selectedIds: unknown[]) {
    const body = await fetchAdminPage(name, targetPage, 100, search);
    const rows: AdminRowDto[] = body.results;
    const missing = relationIds(selectedIds).filter(id => !rows.some(row => row.id === id));
    const selected = await Promise.all(missing.map(id => fetchAdminDetail(name, id)));
    return { count: body.count, results: [...selected, ...rows], page: targetPage, query: search };
  }

  async function open(row?: Row) {
    if (busy) return;
    const requestedResource = resourceName;
    const generation = ++formGeneration.current;
    setBusy(true); setError(""); setNotice(""); setFieldErrors({});
    try {
      const detail = row ? await fetchAdminDetail(requestedResource, row.id) : null;
      const selectedValues: Record<string, unknown> = detail ?? {};
      const loaded = await Promise.all([...new Set(relationFields.map(field => relationResources[field]))].map(async name => {
        const selectedIds = relationIds(relationFields.filter(field => relationResources[field] === name).map(field => selectedValues[field]));
        return [name, await relationPage(name, 1, "", selectedIds)] as const;
      }));
      if (generation !== formGeneration.current) return;
      setRelations(Object.fromEntries(loaded)); setRelationQuery({}); setEditing(detail); setValues(detail ?? Object.fromEntries(resource.fields.map(field => [field, ""])));
    } catch (cause) {
      if (generation === formGeneration.current) setError(cause instanceof Error ? cause.message : "편집 정보를 불러오지 못했어요.");
    } finally {
      if (generation === formGeneration.current) setBusy(false);
    }
  }

  async function searchRelation(name: AdminResourceName, targetPage = 1) {
    const generation = formGeneration.current;
    const request = (relationGeneration.current[name] ?? 0) + 1;
    relationGeneration.current[name] = request;
    setRelationBusy(name); setError("");
    try {
      const selectedIds = relationIds(relationFields.filter(field => relationResources[field] === name).map(field => values[field]));
      const result = await relationPage(name, targetPage, relationQuery[name]?.trim() ?? "", selectedIds);
      if (generation === formGeneration.current && relationGeneration.current[name] === request) setRelations(current => ({ ...current, [name]: result }));
    } catch (cause) {
      if (generation === formGeneration.current && relationGeneration.current[name] === request) setError(cause instanceof Error ? cause.message : "관계 선택지를 검색하지 못했어요.");
    } finally {
      if (generation === formGeneration.current && relationGeneration.current[name] === request) setRelationBusy("");
    }
  }

  async function save() {
    if (busy) return;
    const generation = formGeneration.current;
    const requestedResource = resourceName;
    const currentEditing = editing;
    setBusy(true); setError(""); setNotice(""); setFieldErrors({});
    try {
      const payload = mutationValues(resource.fields, values, currentEditing ? Object.fromEntries(resource.fields.map(field => [field, wireValue(currentEditing, field)])) : undefined);
      if (currentEditing) await updateAdminRow(requestedResource, currentEditing.id, "_etag" in currentEditing ? currentEditing._etag : "", payload);
      else await createAdminRow(requestedResource, payload);
      if (generation !== formGeneration.current) return;
      setNotice("저장했습니다."); setEditing(undefined); setData(null); setReload(item => item + 1);
    } catch (cause) {
      if (generation === formGeneration.current) { setError(cause instanceof Error ? cause.message : "저장하지 못했어요."); setFieldErrors(cause instanceof ApiError ? cause.fields ?? {} : {}); }
    } finally {
      if (generation === formGeneration.current) setBusy(false);
    }
  }

  async function remove() {
    if (!editing || busy || !confirm("이 레코드를 삭제하시겠어요? 참조 데이터는 자동 삭제되지 않습니다.")) return;
    const generation = formGeneration.current;
    const requestedResource = resourceName;
    const currentEditing = editing;
    setBusy(true); setError(""); setNotice("");
    try {
      await deleteAdminRow(requestedResource, currentEditing.id, "_etag" in currentEditing ? currentEditing._etag : "");
      if (generation !== formGeneration.current) return;
      setNotice("삭제했습니다."); setEditing(undefined); setData(null); setReload(item => item + 1);
    } catch (cause) {
      if (generation === formGeneration.current) setError(cause instanceof Error ? cause.message : "삭제하지 못했어요.");
    } finally {
      if (generation === formGeneration.current) setBusy(false);
    }
  }

  function setField(field: string, next: string) {
    setValues(current => ({ ...current, [field]: next }));
    setFieldErrors(current => Object.fromEntries(Object.entries(current).filter(([name]) => name !== field)));
  }

  return <main className={`container ${styles.page}`}><p className="eyebrow">BASEBALL ADMIN</p><h1>야구 데이터 관리</h1><p>19개 DB 자원을 관리합니다. 경기·순위는 적재된 스냅샷이며 실시간 KBO 수집 화면과 별도입니다.</p><Link href="/admin">← 회원 관리</Link>
    <div className={styles.nav}>{groups.map(item => <button type="button" key={item} className={group === item ? styles.active : ""} onClick={() => { setGroup(item); selectResource(adminResources.find(resource => resource.group === item)?.name ?? adminResources[0].name); }}>{item}</button>)}</div>
    <div className={styles.tabs}>{choices.map(item => <button type="button" key={item.name} className={resourceName === item.name ? styles.active : ""} onClick={() => selectResource(item.name)}>{item.label}</button>)}</div>
    <form className={styles.search} onSubmit={event => { event.preventDefault(); setError(""); setData(null); setQuery(String(new FormData(event.currentTarget).get("q") ?? "").trim()); setPage(1); setReload(item => item + 1); }}><input key={resourceName} name="q" aria-label={`${resource.label} 검색`} placeholder="ID 또는 문자열 검색" defaultValue={query} /><button disabled={!data || busy}>검색</button><button type="button" disabled={busy} onClick={() => void open()}>새 레코드</button></form>
    {error && <p className={styles.feedback} role="alert">{error}</p>}{notice && <p className={styles.feedback} role="status">{notice}</p>}{!data && !error && <p role="status">{resource.label} 목록을 불러오고 있어요.</p>}
    {data?.resource === resourceName && <><div className={styles.table}><table><caption className="sr-only">{resource.label} 목록</caption><thead><tr>{resource.fields.slice(0, 6).map(field => <th key={field}>{fieldLabel(field)}</th>)}<th>관리</th></tr></thead><tbody>{data.results.map(row => <tr key={row.id}>{resource.fields.slice(0, 6).map(field => <td key={field}>{String(wireValue(row, field) ?? "—")}</td>)}<td><button type="button" disabled={busy} onClick={() => void open(row)}>편집</button></td></tr>)}{!data.results.length && <tr><td colSpan={7}>적재된 레코드가 없어요.</td></tr>}</tbody></table></div><div className={styles.actions}><button type="button" disabled={page === 1 || busy} onClick={() => { setError(""); setData(null); setPage(page - 1); }}>이전</button><span>{page} / {Math.max(1, Math.ceil(data.count / 30))}</span><button type="button" disabled={page * 30 >= data.count || busy} onClick={() => { setError(""); setData(null); setPage(page + 1); }}>다음</button></div></>}
    {editing !== undefined && <section className={styles.form}><h2>{editing ? `${resource.label} #${editing.id} 편집` : `${resource.label} 생성`}</h2><div className={styles.fields}>{resource.fields.map(field => {
      const relationName = relationResources[field]; const relation = relations[relationName]; const fieldError = fieldErrors[field]; const errorId = `${field}-error`;
      return <label key={field}>{fieldLabel(field)}{relationName ? <><span><input aria-label={`${fieldLabel(field)} 선택지 검색`} value={relationQuery[relationName] ?? ""} onChange={event => setRelationQuery(current => ({ ...current, [relationName]: event.target.value }))} /><button type="button" disabled={relationBusy === relationName} onClick={() => void searchRelation(relationName)}>관계 검색</button></span><select aria-invalid={Boolean(fieldError)} aria-describedby={fieldError ? errorId : undefined} value={formValue(field, values[field])} onChange={event => setField(field, event.target.value)}><option value="">{nullableFields.has(field) ? "없음" : "선택"}</option>{(relation?.results ?? []).map(row => <option key={row.id} value={row.id}>{row.id} · {relationLabel(row)}</option>)}</select>{relation && <span className={styles.relationPages}><button type="button" disabled={relation.page === 1 || relationBusy === relationName} onClick={() => void searchRelation(relationName, relation.page - 1)}>관계 이전</button><small>{relation.page} / {Math.max(1, Math.ceil(relation.count / 100))}</small><button type="button" disabled={relation.page * 100 >= relation.count || relationBusy === relationName} onClick={() => void searchRelation(relationName, relation.page + 1)}>관계 다음</button></span>}</> : booleanFields.has(field) ? <select aria-invalid={Boolean(fieldError)} aria-describedby={fieldError ? errorId : undefined} value={formValue(field, values[field])} onChange={event => setField(field, event.target.value)}><option value="">{nullableFields.has(field) ? "미정" : "선택"}</option><option value="true">예</option><option value="false">아니오</option></select> : <input type={inputType(field)} step={numericFields.has(field) ? "any" : undefined} readOnly={Boolean(editing && field === "id")} aria-invalid={Boolean(fieldError)} aria-describedby={fieldError ? errorId : undefined} value={formValue(field, values[field])} onChange={event => setField(field, event.target.value)} />}{fieldError && <small id={errorId} className={styles.fieldError}>{fieldError.join(" ")}</small>}</label>;
    })}</div><div className={styles.actions}><button type="button" disabled={busy} onClick={() => void save()}>{busy ? "처리 중…" : "저장"}</button>{editing && <button type="button" disabled={busy} onClick={() => void remove()}>삭제</button>}<button type="button" disabled={busy} onClick={() => { formGeneration.current += 1; setEditing(undefined); setError(""); setFieldErrors({}); }}>취소</button></div></section>}
  </main>;
}
