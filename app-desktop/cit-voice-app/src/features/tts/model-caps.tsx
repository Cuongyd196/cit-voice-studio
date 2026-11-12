import { Languages } from "lucide-react";
import type React from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { type LanguageOption, setRequestLanguage } from "./api";

// Kha nang cua mo hinh dang chay, lay tu /health: doc duoc nhung ngon ngu nao
// (Supertonic, Kokoro), co nhan ban giong va the cam xuc khong. Moi tab doc chung mot lua chon ngon
// ngu; api.ts tu gui kem no trong cac request doc.

interface ModelCaps {
  language: string;
  /** Ten ngon ngu dang chon de hien tren the giong ("Tiếng Anh"). */
  languageName: string;
  languages: LanguageOption[];
  /** Doc duoc tieng Viet khong (VieNeu, Supertonic: co; Kokoro: khong). Tu dien
   * phat am viet theo cach doc tieng Viet nen chi dung khi co. */
  readsVietnamese: boolean;
  setLanguage: (code: string) => void;
  supportsCloning: boolean;
  supportsEmotions: boolean;
}

const DEFAULT_LANGUAGE = "en";
const MULTILINGUAL = "Đa ngôn ngữ";

/** Mo ta giong: "Nữ · Đa ngôn ngữ · …" -> "Nữ · Tiếng Anh · …" theo ngon ngu dang chon. */
export function describeVoice(
  description: string,
  languageName: string
): string {
  return languageName
    ? description.replace(MULTILINGUAL, languageName)
    : description;
}

const ModelCapsContext = createContext<ModelCaps>({
  language: "",
  languageName: "",
  languages: [],
  readsVietnamese: true,
  setLanguage: () => undefined,
  supportsCloning: true,
  supportsEmotions: true,
});

export function useModelCaps(): ModelCaps {
  return useContext(ModelCapsContext);
}

export const ModelCapsProvider: React.FC<{
  children: React.ReactNode;
  languages: LanguageOption[];
  supportsCloning: boolean;
  supportsEmotions: boolean;
}> = ({ children, languages, supportsCloning, supportsEmotions }) => {
  // Mac dinh tieng Anh: mo hinh nhieu ngon ngu dung cho van ban tieng nuoc ngoai.
  // "" = tu nhan theo chu.
  const [language, setLanguage] = useState(DEFAULT_LANGUAGE);

  useEffect(() => {
    const valid = languages.some((l) => l.code === language);
    setRequestLanguage(valid ? language : null);
    if (languages.length > 0 && language && !valid) {
      setLanguage(DEFAULT_LANGUAGE);
    }
  }, [language, languages]);

  const languageName =
    languages.find((l) => l.code === language)?.name ?? "Tự nhận ngôn ngữ";
  const readsVietnamese =
    languages.length === 0 || languages.some((l) => l.code === "vi");
  const value = useMemo(
    () => ({
      language,
      languageName,
      languages,
      readsVietnamese,
      setLanguage,
      supportsCloning,
      supportsEmotions,
    }),
    [
      language,
      languageName,
      languages,
      readsVietnamese,
      supportsCloning,
      supportsEmotions,
    ]
  );
  return (
    <ModelCapsContext.Provider value={value}>
      {children}
    </ModelCapsContext.Provider>
  );
};

/** O chon ngon ngu doc; khong hien gi khi mo hinh chi doc tieng Viet (VieNeu). */
export const LanguageSelect: React.FC<{
  className?: string;
  disabled?: boolean;
}> = ({ className, disabled }) => {
  const { language, languages, setLanguage } = useModelCaps();
  if (languages.length === 0) {
    return null;
  }
  return (
    <label
      className={`flex items-center gap-2 text-xs ${className ?? ""}`}
      title="Chọn đúng tiếng của đoạn văn để đọc chuẩn giọng bản xứ (không dịch văn bản). Nút nghe thử cũng đọc câu mẫu bằng tiếng này. Tự nhận: có dấu tiếng Việt thì đọc tiếng Việt, chữ Nhật/Hàn thì đọc tiếng Nhật/Hàn, còn lại đọc tiếng Anh."
    >
      <Languages className="h-4 w-4 shrink-0 text-brand-500" />
      <span className="shrink-0 font-semibold text-foreground/90">
        Ngôn ngữ văn bản
      </span>
      <select
        className="w-full min-w-0 rounded-lg border border-border/80 bg-background px-2.5 py-1.5 outline-none focus:border-brand-500"
        disabled={disabled}
        onChange={(e) => setLanguage(e.target.value)}
        value={language}
      >
        <option value="">Tự nhận theo văn bản</option>
        {languages.map((l) => (
          <option key={l.code} value={l.code}>
            {l.name}
          </option>
        ))}
      </select>
    </label>
  );
};
