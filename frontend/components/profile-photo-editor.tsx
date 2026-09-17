"use client";
import Image from "next/image";
import { useRef, useState } from "react";
import { prepareProfileImage } from "@/lib/profile-image";
import styles from "@/app/mypage/page.module.css";

export function ProfilePhotoEditor({ avatar, onSaved }: { avatar: string; onSaved: (avatar: string) => Promise<void> | void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const photo = draft ?? avatar;
  return <section className={styles.photoEditor} aria-label="프로필 사진 변경">
    <div className={styles.photoPreview}>{photo ? <Image src={photo} alt="프로필 사진 미리보기" width={96} height={96} unoptimized /> : <Image src="/images/default-avatar.svg" alt="기본 프로필 이미지" width={96} height={96} />}</div>
    <div className={styles.photoControls}>
      <h3>프로필 사진</h3>
      <p id="photo-rules">JPG · PNG · WebP, 최대 5MB<br />사진 중앙을 정사각형으로 잘라 원형으로 표시해요.</p>
      <input ref={input} className={styles.hiddenInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label="컴퓨터에서 프로필 사진 선택" aria-describedby="photo-rules" disabled={busy} onChange={async event => {
        const file = event.currentTarget.files?.[0];
        event.currentTarget.value = "";
        if (!file) return;
        setBusy(true); setMessage("");
        try { setDraft(await prepareProfileImage(file)); }
        catch (error) { setMessage(error instanceof Error ? error.message : "사진을 불러오지 못했어요."); }
        finally { setBusy(false); }
      }} />
      <div className={styles.photoButtons}>
        <button type="button" className="button button-secondary" disabled={busy} onClick={() => input.current?.click()}>{busy ? "사진 처리 중…" : "사진 선택"}</button>
        {photo && <button type="button" className="button button-secondary" disabled={busy} onClick={() => { setDraft(""); setMessage(""); }}>기본 이미지로</button>}
        {draft !== null && <><button type="button" className="button button-primary" disabled={busy} onClick={async () => {
          try { setBusy(true); await onSaved(draft); setDraft(null); setMessage("프로필 사진을 저장했어요."); }
          catch (error) { setMessage(error instanceof Error ? error.message : "사진을 저장하지 못했어요."); }
          finally { setBusy(false); }
        }}>사진 저장</button><button type="button" className="button button-secondary" disabled={busy} onClick={() => { setDraft(null); setMessage(""); }}>취소</button></>}
      </div>
      {draft !== null && <p>미리보기를 확인한 뒤 사진 저장을 눌러 주세요.</p>}
      {message && <p role="status">{message}</p>}
    </div>
  </section>;
}
