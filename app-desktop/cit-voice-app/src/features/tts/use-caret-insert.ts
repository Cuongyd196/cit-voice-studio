import { useRef } from "react";
import { insertAtCursor } from "./text-tools";

/**
 * Chèn thẻ cảm xúc / thẻ nghỉ vào đúng chỗ con trỏ của một ô soạn thảo (thay vùng
 * bôi đen, con trỏ đứng ngay sau thẻ). Trước đây thẻ luôn bị nối vào cuối văn bản
 * (người dùng báo, 2026-09). Dùng chung cho TTS Studio và tab Nhân bản giọng.
 */
export function useCaretInsert(
  text: string,
  setText: (value: string) => void,
  disabled = false
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Chưa từng bấm vào ô soạn thảo thì vị trí con trỏ của trình duyệt vô nghĩa
  // (thường là 0): khi đó chèn thẻ vào cuối như trước.
  const touchedRef = useRef(false);

  const onFocus = () => {
    touchedRef.current = true;
  };

  const insertTag = (tag: string) => {
    if (disabled) {
      return;
    }
    const el = textareaRef.current;
    const useCaret = el !== null && touchedRef.current;
    const start = useCaret ? el.selectionStart : text.length;
    const end = useCaret ? el.selectionEnd : text.length;
    const result = insertAtCursor(text, start, end, tag);
    setText(result.text);
    // Đặt con trỏ ngay sau thẻ để bấm tiếp thẻ khác hoặc gõ tiếp đúng chỗ.
    requestAnimationFrame(() => {
      const node = textareaRef.current;
      if (node) {
        node.focus();
        node.setSelectionRange(result.caret, result.caret);
        touchedRef.current = true;
      }
    });
  };

  return { textareaRef, onFocus, insertTag };
}
