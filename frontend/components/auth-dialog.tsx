"use client";

import { ReactNode, useEffect, useRef } from "react";

type AuthDialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

export function AuthDialog({ open, title, onClose, children }: AuthDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (open && dialog && !dialog.open) dialog.showModal();
    if (!open && dialog?.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={dialogRef} className="auth-dialog" aria-labelledby="auth-dialog-title" onCancel={onClose} onClose={onClose}>
      <div className="auth-dialog-heading">
        <h2 id="auth-dialog-title">{title}</h2>
        <button type="button" className="auth-dialog-close" onClick={onClose} aria-label="안내 닫기">×</button>
      </div>
      <div className="auth-dialog-content">{children}</div>
      <button type="button" className="button button-primary auth-submit" onClick={onClose}>확인</button>
    </dialog>
  );
}
