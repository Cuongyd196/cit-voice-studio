import {
  AlertTriangle,
  Code2,
  Cpu,
  ExternalLink,
  Globe,
  Lock,
  Sparkles,
  Volume2,
  Zap,
} from "lucide-react";
import type React from "react";
import type { AppUpdateInfo } from "../api";
import { UpdateCheckButton } from "./AppUpdate";

// Kho ma nguon cua ban CIT Voice Studio (dung o ca the nguon goc lan chan trang).
const REPO_CIT = "https://github.com/Cuongyd196/cit-voice-studio";

interface AboutTabProps {
  apiUrl: string;
  engineName?: string;
  onUpdateChecked: (info: AppUpdateInfo) => void;
  sampleRate?: number;
  /** Phien ban dang chay + ban moi (tu /api/app/update); null khi chua hoi duoc. */
  update: AppUpdateInfo | null;
}

export const AboutTab: React.FC<AboutTabProps> = ({
  apiUrl,
  onUpdateChecked,
  update,
  engineName = "VieNeu-TTS v3 Turbo",
  sampleRate = 48_000,
}) => {
  return (
    <div className="fade-in-50 mx-auto w-full animate-in space-y-6 pb-10 duration-300">
      {/* 1. Hero Banner */}
      <div className="relative overflow-hidden rounded-[14px] border border-border bg-gradient-to-br from-card via-card/95 to-card p-6 shadow-md md:p-8">
        <div className="pointer-events-none absolute top-0 right-0 -mt-8 -mr-8 h-56 w-56 rounded-full bg-brand-500/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-1/3 -mb-12 h-64 w-64 rounded-full bg-cyan-500/10 blur-3xl" />

        <div className="relative flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-brand-500 via-teal-500 to-cyan-500 text-white shadow-brand-500/25 shadow-md">
              <Volume2 className="h-7 w-7" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="font-black text-2xl text-foreground tracking-tight md:text-3xl">
                  CIT Voice Studio
                </h2>
                <span className="rounded-full border border-brand-500/30 bg-brand-500/15 px-2.5 py-0.5 font-bold text-brand-600 text-xs uppercase shadow-xs dark:text-brand-400">
                  Desktop Edition{update ? ` v${update.current}` : ""}
                </span>
              </div>
              <p className="mt-1.5 max-w-2xl text-muted-foreground text-sm leading-relaxed">
                Giải pháp AI chuyển đổi văn bản thành giọng nói (Text-to-Speech)
                và nhân bản giọng nói (Voice Cloning) Tiếng Việt chất lượng cao,
                xử lý hoàn toàn cục bộ (On-Device & Offline).
              </p>
              <div className="mt-3">
                <UpdateCheckButton
                  apiUrl={apiUrl}
                  info={update}
                  onChecked={onUpdateChecked}
                />
              </div>
            </div>
          </div>

          {/* Quick Stats Badges */}
          <div className="flex w-full shrink-0 flex-row gap-2 md:w-auto md:flex-col">
            <div className="flex flex-1 items-center gap-2 rounded-xl border border-border/60 bg-secondary/60 px-3.5 py-2 text-xs md:flex-none">
              <Cpu className="h-4 w-4 text-brand-500" />
              <div>
                <div className="font-semibold text-[12px] text-muted-foreground uppercase">
                  Mô hình AI
                </div>
                <div className="font-bold text-foreground">{engineName}</div>
              </div>
            </div>
            <div className="flex flex-1 items-center gap-2 rounded-xl border border-border/60 bg-secondary/60 px-3.5 py-2 text-xs md:flex-none">
              <Zap className="h-4 w-4 text-cyan-500" />
              <div>
                <div className="font-semibold text-[12px] text-muted-foreground uppercase">
                  Âm thanh
                </div>
                <div className="font-bold text-foreground">
                  {sampleRate / 1000} kHz Hi-Fi
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Key Highlights Cards */}
      <div className="studio-feature-grid">
        <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="shrink-0 rounded-lg bg-brand-500/10 p-2.5 text-brand-500">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h4 className="font-bold text-foreground text-xs uppercase tracking-wide">
              Chất lượng {sampleRate / 1000} kHz Hi-Fi
            </h4>
            <p className="mt-1 text-muted-foreground text-xs leading-relaxed">
              Giọng đọc tự nhiên, trong trẻo với công nghệ VieNeu-Codec.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="shrink-0 rounded-lg bg-cyan-500/10 p-2.5 text-cyan-500">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <h4 className="font-bold text-foreground text-xs uppercase tracking-wide">
              100% Cục bộ & Riêng tư
            </h4>
            <p className="mt-1 text-muted-foreground text-xs leading-relaxed">
              Xử lý On-Device trên máy cá nhân, hoàn toàn không gửi văn bản hay
              audio ra ngoài.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="shrink-0 rounded-lg bg-indigo-500/10 p-2.5 text-indigo-500">
            <Zap className="h-5 w-5" />
          </div>
          <div>
            <h4 className="font-bold text-foreground text-xs uppercase tracking-wide">
              Nhân bản giọng của bạn
            </h4>
            <p className="mt-1 text-muted-foreground text-xs leading-relaxed">
              Thu micro hoặc nhập file âm thanh (MP3, WAV, M4A) có quyền sử
              dụng. Giọng và cam kết chỉ lưu trên máy.
            </p>
          </div>
        </div>
      </div>

      {/* 3. Canh bao su dung: nhan ban giong va gia mao giong la rui ro lon nhat
          cua mot app TTS offline, nen dat truoc phan nguon goc. */}
      <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-5 shadow-xs">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <h3 className="font-bold text-amber-700 text-sm uppercase tracking-wide dark:text-amber-300">
            Cảnh báo
          </h3>
        </div>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-foreground/90 text-sm leading-relaxed">
          <li>
            <strong>Cần có quyền sử dụng giọng:</strong> chỉ nhân bản giọng của
            bạn hoặc giọng được chủ giọng cho phép. Cam kết trong ứng dụng không
            phải xác minh danh tính hay chứng nhận quyền sở hữu.
          </li>
          <li>
            <strong>Không giả mạo giọng người khác</strong> (người thân, người
            nổi tiếng, cán bộ, cơ quan, doanh nghiệp…) để lừa đảo, vay mượn
            tiền, bôi nhọ, xúc phạm hay gây hiểu lầm.
          </li>
          <li>
            <strong>Tôn trọng bản quyền:</strong> văn bản (sách, truyện, báo)
            phải là của bạn hoặc đã được phép sử dụng.
          </li>
          <li>
            Khi đăng tải công khai nội dung mô phỏng giọng người thật,{" "}
            <strong>phải ghi rõ “giọng đọc được tạo bằng AI”</strong>.
          </li>
        </ul>
        <p className="mt-3 border-amber-500/30 border-t pt-2 text-muted-foreground text-xs leading-relaxed">
          Người dùng tự chịu trách nhiệm trước pháp luật về nội dung mình tạo
          ra. Tác giả CIT Voice Studio, VieNeu-TTS, Supertone và Kokoro không
          chịu trách nhiệm với việc sử dụng sai mục đích.
        </p>
      </div>

      {/* 4. Nguồn gốc - một thẻ, không hơn */}
      <div className="space-y-3 rounded-xl border border-border/80 bg-card p-5 shadow-xs">
        <p className="text-foreground/90 text-sm leading-relaxed">
          <strong>CIT Voice Studio</strong> do <strong>Cường IT</strong> phát
          triển, dựa trên <strong>VieNeu-TTS</strong> của tác giả{" "}
          <strong>Phạm Nguyễn Ngọc Bảo</strong> (giọng tiếng Việt). Giọng nước
          ngoài dùng <strong>Supertonic 3</strong> của{" "}
          <strong>Supertone Inc.</strong> và <strong>Kokoro-82M</strong> của{" "}
          <strong>hexgrad</strong>, tải riêng khi bạn chọn. Ứng dụng độc lập,
          không phải sản phẩm chính thức của VieNeu-TTS, Supertone hay Kokoro.
        </p>

        {/* Hai kho ma nguon phai ghi RO cua ai. Truoc day chi co mot lien ket ten
            "GitHub" tro vao repo goc - de hieu nham la repo cua Cuong IT. */}
        <div className="space-y-2 pt-1">
          <div className="flex flex-wrap items-baseline gap-2 text-xs">
            <span className="w-28 shrink-0 text-muted-foreground">
              CIT Voice Studio
            </span>
            <a
              className="inline-flex items-center gap-1 font-bold text-sky-500 transition-colors hover:text-sky-400"
              href={REPO_CIT}
              rel="noreferrer"
              target="_blank"
            >
              <Code2 className="h-3.5 w-3.5" />
              <span>Cuongyd196/cit-voice-studio</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
            <a
              className="inline-flex items-center gap-1 font-bold text-sky-500 transition-colors hover:text-sky-400"
              href="https://me.cuongit.net"
              rel="noreferrer"
              target="_blank"
            >
              <Globe className="h-3.5 w-3.5" />
              <span>me.cuongit.net</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
          </div>

          <div className="flex flex-wrap items-baseline gap-2 text-xs">
            <span className="w-28 shrink-0 text-muted-foreground">
              VieNeu-TTS (gốc)
            </span>
            <a
              className="inline-flex items-center gap-1 font-bold text-brand-600 hover:underline dark:text-brand-400"
              href="https://github.com/pnnbao97/VieNeu-TTS"
              rel="noreferrer"
              target="_blank"
            >
              <Code2 className="h-3.5 w-3.5" />
              <span>pnnbao97/VieNeu-TTS</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
            <a
              className="inline-flex items-center gap-1 font-bold text-amber-600 hover:underline dark:text-amber-400"
              href="https://huggingface.co/pnnbao-ump/VieNeu-TTS"
              rel="noreferrer"
              target="_blank"
            >
              <span>Hugging Face</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
          </div>

          <div className="flex flex-wrap items-baseline gap-2 text-xs">
            <span className="w-28 shrink-0 text-muted-foreground">
              Supertonic 3
            </span>
            <a
              className="inline-flex items-center gap-1 font-bold text-brand-600 hover:underline dark:text-brand-400"
              href="https://github.com/supertone-oss-archive/supertonic"
              rel="noreferrer"
              target="_blank"
            >
              <Code2 className="h-3.5 w-3.5" />
              <span>supertone-oss-archive/supertonic</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
            <a
              className="inline-flex items-center gap-1 font-bold text-amber-600 hover:underline dark:text-amber-400"
              href="https://huggingface.co/supertone-oss-archive/supertonic-3"
              rel="noreferrer"
              target="_blank"
            >
              <span>Hugging Face</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
          </div>

          <div className="flex flex-wrap items-baseline gap-2 text-xs">
            <span className="w-28 shrink-0 text-muted-foreground">
              Kokoro-82M
            </span>
            <a
              className="inline-flex items-center gap-1 font-bold text-brand-600 hover:underline dark:text-brand-400"
              href="https://github.com/hexgrad/kokoro"
              rel="noreferrer"
              target="_blank"
            >
              <Code2 className="h-3.5 w-3.5" />
              <span>hexgrad/kokoro</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
            <a
              className="inline-flex items-center gap-1 font-bold text-amber-600 hover:underline dark:text-amber-400"
              href="https://huggingface.co/hexgrad/Kokoro-82M"
              rel="noreferrer"
              target="_blank"
            >
              <span>Hugging Face</span>
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
          </div>
        </div>

        {/* Apache 2.0 buoc giu thong bao ban quyen TRONG BAN PHAT HANH (file LICENSE
            + NOTICE di kem bo cai), khong buoc hien thi day du trong giao dien. */}
        <p className="border-border/50 border-t pt-1 text-[12px] text-muted-foreground">
          Ứng dụng: mã nguồn mở, Apache 2.0 · VieNeu-TTS: Apache 2.0 ·
          Supertonic 3: OpenRAIL-M (cấm mạo danh, lừa đảo, đăng nội dung AI
          không ghi rõ) · Kokoro-82M: Apache 2.0 (bộ tách âm tải thêm có phần
          GPL-3.0, không nằm trong bộ cài).
        </p>
      </div>

      {/* 5. Footer */}
      <div className="pt-1 text-center">
        <a
          className="inline-flex items-center gap-1.5 font-bold text-muted-foreground text-xs transition-colors hover:text-sky-500"
          href={REPO_CIT}
          rel="noreferrer"
          target="_blank"
        >
          <span>Cường IT</span>
          <ExternalLink className="h-3 w-3 opacity-70" />
        </a>
      </div>
    </div>
  );
};
