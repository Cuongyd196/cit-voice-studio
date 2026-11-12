import { Info } from "lucide-react";
import type React from "react";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

interface InfoTipProps {
  children: React.ReactNode;
  /** Tên tuỳ chọn, dùng cho nhãn đọc màn hình: "Giải thích <label>". */
  label: string;
}

/**
 * Nút ⓘ mở khung giải thích ngay dưới hàng chứa nó (hàng cần `position: relative`).
 * Bấm thay vì rê chuột vì tooltip `title` hiện chậm, bị cắt và không có trên màn cảm ứng.
 */
export function InfoTip({ label, children }: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const panelRef = useRef<HTMLSpanElement>(null);
  const [above, setAbove] = useState(false);

  // Hàng sát đáy cửa sổ (vd. "Ổn định"): không đủ chỗ bên dưới thì mở lên trên.
  useLayoutEffect(() => {
    if (!(open && panelRef.current)) {
      setAbove(false);
      return;
    }
    const rect = panelRef.current.getBoundingClientRect();
    setAbove(rect.bottom > window.innerHeight - 8);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [open]);

  return (
    <span className="info-tip" ref={rootRef}>
      <button
        aria-controls={panelId}
        aria-expanded={open}
        aria-label={`Giải thích ${label}`}
        className="info-tip-button"
        onClick={(e) => {
          // Nút nằm trong <label> của công tắc: không được bật/tắt công tắc.
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        type="button"
      >
        <Info size={15} />
      </button>
      {open && (
        <span
          className="info-tip-panel"
          data-above={above || undefined}
          id={panelId}
          ref={panelRef}
          role="note"
        >
          {children}
        </span>
      )}
    </span>
  );
}
