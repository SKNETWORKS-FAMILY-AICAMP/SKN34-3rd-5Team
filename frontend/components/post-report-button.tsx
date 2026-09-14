"use client";

import { useRef, useState } from "react";
import styles from "./community-board.module.css";

export function PostReportButton({ postNumber }: { postNumber: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  return <div className={styles.reportActions}>
    <button type="button" className={styles.reportButton} onClick={() => dialog.current?.showModal()}><span aria-hidden="true">🚨</span> 신고</button>
    <dialog ref={dialog} className={styles.reportDialog} aria-label="게시글 신고">
      <form method="dialog">
        <h2>게시글 신고</h2>
        <p>게시글 번호 {postNumber}</p>
        <label>신고 사유<select defaultValue="spam"><option value="spam">광고·도배</option><option value="abuse">욕설·비방</option><option value="inappropriate">부적절한 내용</option><option value="privacy">개인정보 노출</option><option value="other">기타</option></select></label>
        <label className={styles.reportReason}>상세 사유<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={50} rows={3} placeholder="신고 사유를 50자 이내로 입력해 주세요." aria-describedby="report-reason-count" /></label>
        <span id="report-reason-count" className={styles.reportReasonCount}>{reason.length}/50자</span>
        <p>신고 접수는 서버 연결 후 이용할 수 있어요.</p>
        <button type="submit">닫기</button>
      </form>
    </dialog>
  </div>;
}
