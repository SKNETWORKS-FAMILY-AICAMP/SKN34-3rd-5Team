"use client";

import { useRef, type ClipboardEvent, type RefObject } from "react";

type ResidentNumberInputProps = {
  front: string;
  back: string;
  onChange: (front: string, back: string) => void;
  onBlur: () => void;
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
};

function digitsOnly(value: string) {
  return value.replace(/\D/g, "");
}

function focusInput(ref: RefObject<HTMLInputElement | null>, select = false) {
  requestAnimationFrame(() => {
    const input = ref.current;
    if (!input || input.disabled) return;
    input.focus();
    if (select) input.select();
    else input.setSelectionRange(input.value.length, input.value.length);
  });
}

export function ResidentNumberInput({
  front,
  back,
  onChange,
  onBlur,
  disabled = false,
  invalid = false,
  describedBy,
}: ResidentNumberInputProps) {
  const frontRef = useRef<HTMLInputElement>(null);
  const leadingRef = useRef<HTMLInputElement>(null);
  const secretRef = useRef<HTMLInputElement>(null);
  const leading = back.slice(0, 1);
  const secret = back.slice(1, 7);

  function pasteFront(event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    const pasted = digitsOnly(event.clipboardData.getData("text"));
    if (!pasted) return;

    if (pasted.length > 6) {
      const nextBack = pasted.slice(6, 13);
      onChange(pasted.slice(0, 6), nextBack);
      focusInput(nextBack ? secretRef : leadingRef);
      return;
    }

    const input = event.currentTarget;
    const start = input.selectionStart ?? front.length;
    const end = input.selectionEnd ?? start;
    const nextFront = `${front.slice(0, start)}${pasted}${front.slice(end)}`.slice(0, 6);
    onChange(nextFront, back);
    if (nextFront.length === 6) focusInput(leadingRef, true);
  }

  function pasteLeading(event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    const pasted = digitsOnly(event.clipboardData.getData("text")).slice(0, 7);
    if (!pasted) return;
    onChange(front, pasted.length > 1 ? pasted : pasted + secret);
    focusInput(secretRef, pasted.length === 1);
  }

  return (
    <div
      className="resident-number-input"
      role="group"
      aria-label="주민등록번호"
      data-invalid={invalid}
      aria-describedby={describedBy}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onBlur();
      }}
    >
      <input
        ref={frontRef}
        id="signup-resident-front"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        aria-label="주민등록번호 앞자리"
        aria-invalid={invalid}
        aria-describedby={describedBy}
        placeholder="앞 6자리"
        maxLength={6}
        value={front}
        required
        disabled={disabled}
        onPaste={pasteFront}
        onChange={(event) => {
          const nextFront = digitsOnly(event.target.value).slice(0, 6);
          onChange(nextFront, back);
          if (nextFront.length === 6 && front.length < 6) focusInput(leadingRef, true);
        }}
      />
      <span className="resident-number-dash" aria-hidden="true">-</span>
      <div className="resident-number-back" data-invalid={invalid || undefined}>
        <input
          ref={leadingRef}
          id="signup-resident-back"
          className="resident-number-leading"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          aria-label="주민등록번호 뒷자리 첫 숫자"
          aria-invalid={invalid}
          aria-describedby={describedBy}
          placeholder="0"
          maxLength={1}
          value={leading}
          required
          disabled={disabled}
          onPaste={pasteLeading}
          onChange={(event) => {
            const nextLeading = digitsOnly(event.target.value).slice(0, 1);
            // Clearing the first digit clears its suffix, keeping hidden digits hidden.
            onChange(front, nextLeading ? nextLeading + secret : "");
            if (nextLeading) focusInput(secretRef, true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Backspace" && !leading) {
              event.preventDefault();
              focusInput(frontRef);
            }
          }}
        />
        <input
          ref={secretRef}
          id="signup-resident-secret"
          className="resident-number-secret"
          type="password"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          aria-label="주민등록번호 뒷자리 나머지 6자리"
          aria-invalid={invalid}
          aria-describedby={describedBy}
          placeholder="••••••"
          maxLength={6}
          value={secret}
          required
          disabled={disabled || !leading}
          onPaste={(event) => {
            event.preventDefault();
            const pasted = digitsOnly(event.clipboardData.getData("text"));
            if (!pasted) return;
            const input = event.currentTarget;
            const start = input.selectionStart ?? secret.length;
            const end = input.selectionEnd ?? start;
            const nextSecret = `${secret.slice(0, start)}${pasted}${secret.slice(end)}`.slice(0, 6);
            onChange(front, leading + nextSecret);
          }}
          onChange={(event) => onChange(front, leading + digitsOnly(event.target.value).slice(0, 6))}
          onKeyDown={(event) => {
            const input = event.currentTarget;
            if (event.key === "Backspace" && input.selectionStart === 0 && input.selectionEnd === 0) {
              event.preventDefault();
              focusInput(leadingRef, true);
            }
          }}
        />
      </div>
    </div>
  );
}
