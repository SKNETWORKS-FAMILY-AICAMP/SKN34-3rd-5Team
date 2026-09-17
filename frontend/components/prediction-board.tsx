"use client";

import { useEffect, useState } from "react";
import { CommunityNavigation } from "./community-navigation";
import { useMemberAuth } from "@/lib/member-auth";
import { teamBoards } from "@/lib/team-community";
import { fetchPredictionGame, fetchPredictionGames, setPredictionVote, type PredictionChoice, type PredictionGame } from "@/lib/predictions-api";
import styles from "./prediction-board.module.css";

const statusLabels: Record<PredictionGame["status"], string> = {
  scheduled: "경기 예정", live: "경기 중", final: "경기 종료", cancelled: "경기 취소",
  postponed: "경기 연기", suspended: "경기 중단", unknown: "상태 확인 중",
};

const koreaDate = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());

function gameMessage(game: PredictionGame) {
  if (game.voided) return "취소·연기로 투표가 무효 처리되었어요.";
  if (game.status === "final") return game.result === "draw" ? "무승부로 종료되었어요." : `${game.result === "home" ? game.home.name : game.away.name} 승리`;
  if (game.stale) return "최신 경기 정보를 확인 중이라 투표할 수 없어요.";
  if (game.locked) return "투표가 마감되었어요.";
  return "마감 전에는 선택을 바꾸거나 취소할 수 있어요.";
}

export function PredictionBoard({ initialDate = "", initialTeam = "", initialGameId = "" }: { initialDate?: string; initialTeam?: string; initialGameId?: string }) {
  const { status: authStatus, user } = useMemberAuth();
  const [date, setDate] = useState(initialDate || koreaDate);
  const [team, setTeam] = useState(teamBoards.some(value => value.code === initialTeam.toUpperCase()) ? initialTeam.toUpperCase() : "");
  const [directGameId, setDirectGameId] = useState(initialGameId);
  const [games, setGames] = useState<PredictionGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const authenticated = authStatus === "authenticated";

  useEffect(() => {
    if (authStatus === "loading") return;
    const controller = new AbortController();
    let current = true;
    const request = directGameId
      ? fetchPredictionGame(directGameId, authenticated, controller.signal).then(game => [game])
      : fetchPredictionGames({ date, team }, authenticated, controller.signal);
    request.then(value => { if (current) setGames(value); })
      .catch(value => { if (current && !controller.signal.aborted) { setGames([]); setError(value instanceof Error ? value.message : "경기 정보를 불러오지 못했어요."); } })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [authStatus, authenticated, user?.id, date, team, directGameId]);

  async function vote(game: PredictionGame, choice: PredictionChoice) {
    if (!authenticated) { setError("로그인 후 투표할 수 있어요."); return; }
    setPending(game.gameId); setError("");
    try {
      const updated = await setPredictionVote(game.gameId, game.myChoice === choice ? null : choice);
      setGames(current => current.map(value => value.gameId === updated.gameId ? updated : value));
    } catch (value) {
      setError(value instanceof Error ? value.message : "투표를 저장하지 못했어요.");
    } finally { setPending(""); }
  }

  const changeFilters = (nextDate: string, nextTeam: string) => { setLoading(true); setError(""); setDirectGameId(""); setDate(nextDate); setTeam(nextTeam); };

  return (
    <main className={`container ${styles.page}`}>
      <p className={styles.eyebrow}>COMMUNITY</p>
      <h1>승부 예측</h1>
      <p className={styles.description}>오늘의 KBO 경기에서 이길 팀을 선택해 보세요. 경기 시작 시각은 서버 기준으로 마감돼요.</p>
      <CommunityNavigation active="predictions" />
      <div className={styles.filters}>
        <label>날짜<input type="date" value={date} onChange={event => changeFilters(event.target.value, team)} /></label>
        <label>팀<select value={team} onChange={event => changeFilters(date, event.target.value)}><option value="">전체 팀</option>{teamBoards.map(value => <option key={value.code} value={value.code}>{value.shortName}</option>)}</select></label>
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {loading ? <p className={styles.state} role="status">경기 정보를 불러오고 있어요.</p> : games.length === 0 ? <p className={styles.state}>선택한 조건의 경기가 없어요.</p> : (
        <div className={styles.grid} aria-live="polite">
          {games.map(game => {
            const disabled = pending === game.gameId || game.locked || game.voided || game.stale;
            return <article className={styles.card} key={game.gameId} id={`game-${game.gameId}`}>
              <header><span>{statusLabels[game.status]}</span><time dateTime={game.startsAt ?? game.date}>{game.startsAt ? new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit" }).format(new Date(game.startsAt)) : "시간 미정"}</time><small>{game.stadium}</small></header>
              <div className={styles.teams}>
                {(["away", "home"] as const).map(side => {
                  const opponent = game[side], percent = game.votes[`${side}Percent`], count = game.votes[side];
                  return <div className={styles.team} key={side}>
                    <span>{side === "away" ? "원정" : "홈"}</span><strong>{opponent.name}</strong>
                    {opponent.score !== null && <b className={styles.score}>{opponent.score}</b>}
                    <button type="button" aria-pressed={game.myChoice === side} disabled={disabled} onClick={() => void vote(game, side)}>{game.myChoice === side ? "선택됨" : `${opponent.name} 승`}</button>
                    <div className={styles.bar} aria-label={`${opponent.name} ${percent}%`}><span style={{ width: `${percent}%` }} /></div>
                    <small>{count}표 · {percent}%</small>
                  </div>;
                })}
              </div>
              <footer><span>{game.votes.total}명 참여</span><p>{gameMessage(game)}</p></footer>
            </article>;
          })}
        </div>
      )}
    </main>
  );
}
