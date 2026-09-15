"use client";
import Link from "next/link";
import Image from "next/image";
import { MemberAccountSettings, PasswordChangeButton } from "@/components/member-account-settings";
import { ProfilePhotoEditor } from "@/components/profile-photo-editor";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useMemberAuth, type MemberUser } from "@/lib/member-auth";
import { retryRoutes, useRoutes, useLikedRoutes, useRoutesError, useRoutesReady } from "@/lib/routes";
import { teamBoards } from "@/lib/team-community";
import { nextNicknameChangeAt } from "@/lib/member-policy";
import { memberError, memberFetch } from "@/lib/member-auth-request";
import { RouteCard } from "@/components/route-card";
import styles from "./page.module.css";

async function patchUser(payload: Record<string, unknown>, signal = AbortSignal.timeout(15000)): Promise<MemberUser> {
  let response: Response;
  try { response = await memberFetch("/api/auth/user", { method: "PATCH", headers: { "Content-Type": "application/json" }, signal, body: JSON.stringify(payload) }); }
  catch (error) { throw new Error(error instanceof DOMException && error.name === "TimeoutError" ? "요청 결과를 확인하지 못했어요. 새로고침해 저장 상태를 확인해 주세요." : "회원 서버에 연결하지 못했어요."); }
  const result = await response.json();
  if (!response.ok) throw new Error(memberError(result, "회원 정보를 저장하지 못했어요."));
  return result;
}

function MyPageContent() {
  const { status, user, setUser } = useMemberAuth();
  const router = useRouter(), search = useSearchParams();
  const selected = search.get("tab");
  const tab = selected === "likes" || selected === "profile" || selected === "posts" ? selected : "courses";
  const ready = useRoutesReady();
  const routes = useRoutes();
  const loadError = useRoutesError();
  const likes = useLikedRoutes();
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const saveRequest = useRef<AbortController | null>(null);
  const [loadedAt] = useState(() => Date.now());
  useEffect(() => () => saveRequest.current?.abort(), []);
  if (status === "loading") return <main className={`container ${styles.page}`}><p role="status">회원 화면을 불러오고 있어요.</p></main>;
  if (status === "unavailable") return <main className={`container ${styles.page}`}><h1>마이페이지</h1><p className={styles.note}>회원 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.</p></main>;
  if (!user) return <main className={`container ${styles.page}`}><h1>마이페이지</h1><p className={styles.note}>로그인 후 이용할 수 있어요.</p><Link className="button button-primary" href="/login">로그인</Link></main>;
  if (!ready && (tab === "courses" || tab === "likes")) return <main className={`container ${styles.page}`}><p role="status">코스 목록을 불러오고 있어요.</p></main>;
  const team = teamBoards.find(item => item.code === user.team_code);
  const nextChange = nextNicknameChangeAt(user.nickname_changed_at);
  const nicknameLocked = Boolean(nextChange && loadedAt < Date.parse(nextChange));
  const displayName = user.nickname || user.username;
  const own = routes.filter(route => route.owned);
  const liked = routes.filter(route => likes.includes(route.id));
  const visible = tab === "likes" ? liked : own;
  return <main className={`container ${styles.page}`}>
    <p className="eyebrow">MY PAGE</p><h1>마이페이지</h1>
    <section className={styles.profile} aria-label="내 프로필"><div className={styles.avatarWrap}><div className={styles.avatar} aria-hidden="true">{user.avatar ? <Image src={user.avatar} alt="" width={60} height={60} unoptimized /> : <Image src="/images/default-avatar.svg" alt="" width={60} height={60} />}</div>{team && <span className={styles.teamBadge} title={team.name}><Image src={`/images/teams/${team.code.toLowerCase()}.svg`} alt={`응원팀 ${team.name}`} width={22} height={22} /></span>}</div><div><h2 className={styles.memberName}>{displayName}님</h2><p>일반 회원 · {team?.name ?? "응원팀 미설정"}</p></div><Link href="/routes/new" className="button button-primary">코스 만들기</Link></section>
    <p className={styles.note}>계정·프로필 설정은 서버에 저장돼요. 새 코스는 공개되며 편집 권한만 이 브라우저에 저장돼요. 이전 버전 코스는 다시 저장하기 전까지 이 브라우저에만 남아요.</p>
    {loadError && <p className={styles.note} role="alert">{loadError} 이전 버전 코스만 표시될 수 있어요. <button type="button" onClick={() => void retryRoutes()}>다시 불러오기</button></p>}
    <nav className={styles.tabs} aria-label="마이페이지 메뉴">
      {[["courses",`내 코스 (${own.length})`],["likes",`찜한 코스 (${liked.length})`],["posts","내가 쓴 글"],["profile","회원 정보"]].map(([value, label]) => <button key={value} type="button" aria-pressed={tab === value} onClick={() => router.push(`/mypage?tab=${value}`, { scroll: false })}>{label}</button>)}
    </nav>
    {tab === "posts" ? <section className={styles.empty}><h2>아직 계정 데이터와 연결되지 않았어요</h2><p>이 브라우저의 게시글을 실회원 소유 데이터로 표시하지 않아요.</p></section> : tab === "profile" ? <section className={styles.settings}><h2>회원정보 수정</h2>
      <ProfilePhotoEditor avatar={user.avatar} onSaved={async avatar => { const updated = await patchUser({ avatar }); setUser(updated, user.id); }} />
      <form key={`${user.nickname}:${user.team_code}:${user.email}`} onSubmit={async event => {
        event.preventDefault(); if (saveRequest.current) return; const values = new FormData(event.currentTarget), controller = new AbortController(); saveRequest.current = controller; setSaving(true); setMessage("");
        try { const updated = await patchUser({ nickname: String(values.get("nickname") ?? ""), team_code: String(values.get("teamCode") ?? ""), first_name: String(values.get("firstName") ?? ""), birth_date: String(values.get("birthDate") ?? "") || null, gender: String(values.get("gender") ?? "") || null, notifications: { comments: values.has("notify-comments"), courses: values.has("notify-courses"), announcements: values.has("notify-announcements") }, visibility: { courses: values.has("public-courses"), posts: values.has("public-posts"), likes: values.has("public-likes") } }, AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])); if (setUser(updated, user.id)) setMessage("변경사항을 저장했어요."); }
        catch (cause) { setMessage(cause instanceof Error ? cause.message : "저장하지 못했어요."); }
        finally { saveRequest.current = null; setSaving(false); }
      }}>
        <label>이름<input name="firstName" defaultValue={user.first_name} maxLength={150} /></label>
        <label>생년월일<input name="birthDate" type="date" defaultValue={user.birth_date ?? ""} /></label>
        <label>성별<select name="gender" defaultValue={user.gender ?? ""}><option value="">선택 안 함</option><option value="M">남성</option><option value="F">여성</option></select></label>
        <label>닉네임<input className={styles.nicknameInput} name="nickname" defaultValue={user.nickname || "야구팬"} maxLength={12} pattern="[A-Za-z가-힣]{1,12}" title="한글·영문만 1~12자" required readOnly={nicknameLocked} aria-describedby="nickname-rule" /></label>
        <p id="nickname-rule" className={styles.nicknameRule}>{nicknameLocked && nextChange ? `다음 변경 가능: ${new Date(nextChange).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}` : "한글·영문만 최대 12자. 변경 후 6개월 동안 다시 바꿀 수 없어요."}</p>
        <PasswordChangeButton />
        <MemberAccountSettings user={user} onChanged={updated => { setUser(updated, user.id); }} />
        <label>응원팀<select name="teamCode" defaultValue={user.team_code}><option value="">선택 안 함</option>{teamBoards.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label>
        <button className="button button-primary" type="submit" disabled={saving}>{saving ? "저장 중…" : "변경사항 저장"}</button>{message && <p role="status">{message}</p>}
      </form>
    </section> : <section aria-label={tab === "likes" ? "찜한 코스" : "내 코스"}>
      {visible.length ? <div className={styles.grid}>{visible.map(route => <div key={route.id}><RouteCard route={route} />{tab === "courses" && <div className={styles.actions}><Link href={`/routes/new?edit=${encodeURIComponent(route.id)}`}>수정하기</Link><Link href={`/routes/${encodeURIComponent(route.id)}`}>상세 보기</Link></div>}</div>)}</div> : <div className={styles.empty}><h2>{tab === "likes" ? "아직 찜한 코스가 없어요" : "아직 저장한 코스가 없어요"}</h2><p>{tab === "likes" ? "마음에 드는 코스에 좋아요를 눌러보세요." : "지도에서 장소를 골라 첫 코스를 만들어보세요."}</p><Link className="button button-primary" href={tab === "likes" ? "/routes" : "/routes/new"}>{tab === "likes" ? "코스 둘러보기" : "코스 만들기"}</Link></div>}
    </section>}
  </main>;
}

export default function MyPage() { return <Suspense fallback={<main className="container"><p>회원 화면을 불러오고 있어요.</p></main>}><MyPageContent /></Suspense>; }
