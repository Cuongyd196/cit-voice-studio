import {
  AlertCircle,
  CheckCircle2,
  Download,
  Play,
  Sliders,
  Sparkles,
  Users,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { convertToMp3, synthesizeConversation } from "../api";
import { downloadBlobAsFile } from "../audio-engine";
import { LanguageSelect, useModelCaps } from "../model-caps";
import type { HistoryEntry, VoiceOption } from "../types";
import { groupVoices, voiceOptionLabel } from "../voice-label";
import { AdvancedGeneration, DEFAULT_TEMPERATURE } from "./AdvancedGeneration";

interface ConversationTabProps {
  /** Tab dang hien. Tab an van giu trong DOM nen phai tu dung audio khi bi an. */
  active: boolean;
  apiUrl: string;
  onAddHistory: (entry: HistoryEntry) => void;
  /** Kich ban khoi phuc tu lich su; doi `key` moi lan de nap lai ca kich ban cu. */
  restoredScript?: { key: number; script: string } | null;
  voices: VoiceOption[];
}

const SAMPLE_SCRIPTS = [
  {
    title: "Phỏng vấn Podcast AI",
    script: `[Host]: [hắng giọng] Xin chào quý thính giả đã quay trở lại với Podcast Công nghệ CIT! Hôm nay chúng ta có sự tham gia của chuyên gia AI.
[Khách mời]: Chào anh Host và các bạn thính giả. [cười] Rất vui được chia sẻ cùng mọi người về công nghệ giọng nói VieNeu-TTS v3 Turbo.
[Host]: Anh có thể cho biết điểm đột phá lớn nhất của phiên bản này là gì không?
[Khách mời]: Đó chính là khả năng chạy thời gian thực trên CPU thông thường và hỗ trợ clone giọng siêu nhanh chỉ trong vài giây!`,
  },
  {
    title: "Kể chuyện đối thoại",
    script: `[Dẫn chuyện]: Ngày xưa, trong một khu rừng bạt ngàn lá vàng, có một chú Thỏ trắng và một bác Rùa già thông thái.
[Thỏ con]: Bác Rùa ơi! [cười] Bác có muốn chạy thi lên đỉnh đồi với cháu không?
[Bác Rùa]: [thở dài] Được thôi Thỏ nhỏ, nhưng đường xa vạn dặm, cần kiên trì mới về đích được cháu nhé!`,
  },
  {
    title: "Tư vấn khách hàng",
    script: `[Tư vấn viên]: Dạ CIT Voice Studio xin nghe! Em có thể hỗ trợ gì cho anh chị ạ?
[Khách hàng]: [hắng giọng] Chào bạn, mình muốn tích hợp giọng đọc AI vào phần mềm làm video ngắn tự động.
[Tư vấn viên]: [cười] Dạ vâng, bên em có sẵn API tốc độ cao, hỗ trợ xuất cả chuẩn WAV phòng thu và MP3 nén rất tiện lợi anh nhé!`,
  },
  {
    title: "Tọa đàm 4 người",
    script: `[MC]: Kính chào quý vị đến với buổi tọa đàm về chuyển đổi số trong giáo dục. Hôm nay chúng ta có ba vị khách mời.
[Cô giáo]: Xin chào mọi người. Ở trường tôi, học sinh đã quen với việc nộp bài và nghe giảng trực tuyến.
[Phụ huynh]: [cười] Còn phụ huynh chúng tôi thì vui vì theo dõi được việc học của con ngay trên điện thoại.
[Học sinh]: Em thích nhất là nghe lại bài giảng bằng giọng đọc khi ôn thi ạ.
[MC]: Cảm ơn ba vị khách mời. Hẹn gặp lại quý vị trong số tiếp theo!`,
  },
];

// Ban tieng Anh cho mo hinh nhieu ngon ngu (Supertonic), dung the cam xuc rieng cua no.
const SAMPLE_SCRIPTS_FOREIGN = [
  {
    title: "Phỏng vấn Podcast AI",
    script: `[Host]: Welcome back to the CIT Tech Podcast! Today we are joined by an AI expert.
[Guest]: Thanks for having me. <laugh> I'm happy to talk about AI voice technology.
[Host]: What is the biggest breakthrough in this new version?
[Guest]: It runs in real time on an ordinary computer, with no graphics card needed!`,
  },
  {
    title: "Kể chuyện đối thoại",
    script: `[Narrator]: Long ago, in a forest full of golden leaves, there lived a little white rabbit and a wise old turtle.
[Rabbit]: Mister Turtle! <laugh> Do you want to race me to the top of the hill?
[Turtle]: <sigh> All right, little one. But the road is long, and only patience will get you there.`,
  },
  {
    title: "Tư vấn khách hàng",
    script: `[Agent]: Thank you for calling CIT Voice Studio! How can I help you today?
[Customer]: Hi, I'd like to add an AI voice to my short video app.
[Agent]: <laugh> Of course! We have a fast API that exports both studio-quality WAV and compact MP3.`,
  },
  {
    title: "Tọa đàm 4 người",
    script: `[Host]: Welcome to our panel on digital learning. Today we have three guests.
[Teacher]: Hello everyone. At my school, students now hand in homework and watch lessons online.
[Parent]: <laugh> And we parents can follow our children's progress right on our phones.
[Student]: My favorite part is listening to lessons again before exams.
[Host]: Thank you all. See you in the next episode!`,
  },
];

const TRAILING_SPACE = /\s+$/;

/** Tên "Người N" chưa dùng, để nút "Thêm nhân vật" không trùng nhân vật đã có. */
function nextSpeakerName(existing: string[]): string {
  const taken = new Set(existing.map((name) => name.toLowerCase()));
  let n = existing.length + 1;
  while (taken.has(`người ${n}`)) {
    n += 1;
  }
  return `Người ${n}`;
}

const SPEAKER_COLORS = [
  "from-pink-500 to-rose-500",
  "from-cyan-500 to-blue-500",
  "from-brand-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-purple-500 to-violet-500",
  "from-indigo-500 to-sky-500",
];

export const ConversationTab: React.FC<ConversationTabProps> = ({
  active,
  apiUrl,
  voices,
  onAddHistory,
  restoredScript,
}) => {
  const multilingual = useModelCaps().languages.length > 0;
  const samples = multilingual ? SAMPLE_SCRIPTS_FOREIGN : SAMPLE_SCRIPTS;
  const [script, setScript] = useState<string>(SAMPLE_SCRIPTS[0].script);

  // Doi mo hinh thi doi kich ban mau mac dinh theo, nhung chi khi nguoi dung chua sua.
  useEffect(() => {
    setScript((current) => {
      const isDefault =
        current === SAMPLE_SCRIPTS[0].script ||
        current === SAMPLE_SCRIPTS_FOREIGN[0].script;
      return isDefault ? samples[0].script : current;
    });
  }, [samples]);

  useEffect(() => {
    if (restoredScript) {
      setScript(restoredScript.script);
    }
  }, [restoredScript]);

  const scriptRef = useRef<HTMLTextAreaElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    if (!active) {
      audioRef.current?.pause();
    }
  }, [active]);
  const [speakerMapping, setSpeakerMapping] = useState<Record<string, string>>(
    {}
  );
  const [silenceDuration, setSilenceDuration] = useState<number>(0.4);
  const [speed, setSpeed] = useState<number>(1.0);
  const [temperature, setTemperature] = useState(DEFAULT_TEMPERATURE);

  // Generation state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [outputBlob, setOutputBlob] = useState<Blob | null>(null);
  const [outputUrl, setOutputUrl] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState<number | null>(null);
  const [genDuration, setGenDuration] = useState<number | null>(null);
  const [turnsCount, setTurnsCount] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // URL kết quả còn được dùng bởi lịch sử và thanh phát chung khi đổi tab.

  // Extract unique speakers from script
  const detectedSpeakers = useMemo(() => {
    const pattern = /^\s*(?:\[([^\]]+)\]|([^:]+))\s*:/gm;
    const speakers = new Set<string>();
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(script)) !== null) {
      const spk = (match[1] || match[2]).trim();
      if (spk) {
        speakers.add(spk);
      }
    }
    return Array.from(speakers);
  }, [script]);

  // Nhân vật bị app tự đổi giọng (giọng cũ đã bị xóa / đổi model): báo cho người
  // dùng, nếu không bài podcast ra đọc sai giọng mà không ai biết.
  const [replacedVoices, setReplacedVoices] = useState<Record<string, string>>(
    {}
  );
  const mappingRef = useRef(speakerMapping);
  mappingRef.current = speakerMapping;
  // Tên giọng của danh sách trước, để báo được tên giọng vừa mất.
  const voiceNamesRef = useRef<Record<string, string>>({});

  // Gán giọng cho nhân vật mới, và gán lại cho nhân vật có giọng không còn.
  useEffect(() => {
    if (voices.length === 0) {
      return;
    }
    const next = { ...mappingRef.current };
    const replaced: Record<string, string> = {};
    let changed = false;
    detectedSpeakers.forEach((spk, idx) => {
      if (voices.some((voice) => voice.id === next[spk])) {
        return;
      }
      // Distribute distinct voices
      const assignedVoice = voices[idx % voices.length];
      const oldId = next[spk];
      if (oldId) {
        const oldName = voiceNamesRef.current[oldId] ?? oldId;
        replaced[spk] =
          `Giọng "${oldName}" của ${spk} không còn, đã đổi sang "${assignedVoice.name}".`;
      }
      next[spk] = assignedVoice.id;
      changed = true;
    });
    voiceNamesRef.current = Object.fromEntries(
      voices.map((voice) => [voice.id, voice.name])
    );
    if (changed) {
      setSpeakerMapping(next);
    }
    if (Object.keys(replaced).length > 0) {
      setReplacedVoices((prev) => ({ ...prev, ...replaced }));
    }
  }, [detectedSpeakers, voices]);

  // Người dùng tưởng hội thoại chỉ có 2 người: thêm sẵn một dòng nhân vật mới ở cuối
  // kịch bản và đặt con trỏ vào đó để gõ lời thoại ngay.
  const handleAddSpeaker = () => {
    const line = `[${nextSpeakerName(detectedSpeakers)}]: `;
    const trimmed = script.replace(TRAILING_SPACE, "");
    const next = trimmed ? `${trimmed}\n${line}` : line;
    setScript(next);
    requestAnimationFrame(() => {
      const el = scriptRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(next.length, next.length);
        el.scrollTop = el.scrollHeight;
      }
    });
  };

  // Handle Generate Conversation
  const handleGenerate = async () => {
    if (!script.trim()) {
      setErrorMessage("Vui lòng nhập kịch bản hội thoại!");
      return;
    }

    setIsGenerating(true);
    setErrorMessage(null);
    setReplacedVoices({});

    try {
      // Không âm thầm đổi sang giọng mặc định nếu giọng đã bị xóa hoặc đổi model.
      if (
        detectedSpeakers.some(
          (speaker) =>
            !voices.some((voice) => voice.id === speakerMapping[speaker])
        )
      ) {
        throw new Error("Vui lòng chọn giọng hợp lệ cho từng nhân vật.");
      }
      const validMapping = Object.fromEntries(
        Object.entries(speakerMapping).filter(([, id]) =>
          voices.some((v) => v.id === id)
        )
      );
      const res = await synthesizeConversation(apiUrl, {
        script,
        speakerMapping: validMapping,
        silenceDuration,
        speed,
        temperature,
        format: "wav",
      });

      setOutputBlob(res.blob);
      const url = URL.createObjectURL(res.blob);
      setOutputUrl(url);
      setElapsedSec(res.elapsedSeconds);
      setGenDuration(res.durationSeconds);
      setTurnsCount(res.turnsCount || detectedSpeakers.length);

      onAddHistory({
        id: `conv_${Date.now()}`,
        text: script,
        voiceId: "multi_speaker",
        voiceName: `Hội thoại (${detectedSpeakers.join(", ")})`,
        timestamp: Date.now(),
        durationSeconds: res.durationSeconds,
        audioBlobUrl: url,
        audioBlob: res.blob,
        mode: "conversation",
        format: "wav",
      });
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi tổng hợp hội thoại.");
    } finally {
      setIsGenerating(false);
    }
  };

  // Download WAV
  const handleDownloadWav = async () => {
    if (!outputBlob) {
      return;
    }
    await downloadBlobAsFile(outputBlob, `cit_podcast_${Date.now()}.wav`);
  };

  // Download MP3
  const handleDownloadMp3 = async () => {
    if (!outputBlob) {
      return;
    }
    try {
      const mp3Blob = await convertToMp3(apiUrl, outputBlob);
      await downloadBlobAsFile(mp3Blob, `cit_podcast_${Date.now()}.mp3`);
    } catch {
      handleDownloadWav();
    }
  };

  return (
    <div className="studio-tab-grid studio-conversation-layout fade-in-50 animate-in duration-300">
      {/* Left Column: Script Editor (7 cols) */}
      <div className="studio-span-7 flex flex-col space-y-4">
        <div className="studio-tab-card flex flex-1 flex-col space-y-3 rounded-[14px] border border-border bg-card p-5 shadow-sm">
          <div className="studio-section-heading flex items-center justify-between border-border/60 border-b pb-3">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-brand-500" />
              <h3 className="font-bold text-foreground text-sm">
                Kịch bản Hội thoại / Podcast
              </h3>
            </div>

            {/* Character count & detected speakers count */}
            <div className="flex items-center gap-2 font-mono text-muted-foreground text-xs">
              <span>{detectedSpeakers.length} nhân vật</span>
              <span>·</span>
              <span>{script.length} ký tự</span>
            </div>
          </div>

          {/* Preset Sample Scripts */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="flex items-center gap-1 text-[12px] text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              Kịch bản mẫu:
            </span>
            {samples.map((item) => (
              <button
                className="rounded-full border border-border/60 bg-secondary/80 px-2.5 py-1 text-foreground/80 text-xs transition-all hover:bg-secondary hover:text-foreground active:scale-95"
                disabled={isGenerating}
                key={item.title}
                onClick={() => setScript(item.script)}
                type="button"
              >
                {item.title}
              </button>
            ))}
          </div>

          {/* Script Textarea */}
          <div className="studio-conversation-editor relative flex flex-col pt-1">
            <textarea
              className="w-full flex-1 resize-none rounded-xl border border-border/80 bg-secondary/20 p-3.5 font-sans text-[14px] text-foreground leading-relaxed outline-none focus:border-brand-500"
              disabled={isGenerating}
              onChange={(e) => setScript(e.target.value)}
              placeholder={
                "Nhập kịch bản đối thoại theo cú pháp:\n[Người 1]: Lời thoại nhân vật 1...\n[Người 2]: Lời thoại nhân vật 2...\n[Người 3]: Lời thoại nhân vật 3...\nThêm bao nhiêu nhân vật cũng được."
              }
              ref={scriptRef}
              value={script}
            />
          </div>

          <div className="flex items-center justify-between gap-2 text-[12px] text-muted-foreground">
            <span>
              Mỗi tên mới trong <code>[Tên]:</code> là một nhân vật, không giới
              hạn số người.
            </span>
            <button
              className="flex-shrink-0 rounded-full border border-border/60 bg-secondary/80 px-2.5 py-1 font-medium text-foreground/80 text-xs transition-all hover:bg-secondary hover:text-foreground active:scale-95 disabled:opacity-50"
              disabled={isGenerating}
              onClick={handleAddSpeaker}
              type="button"
            >
              + Thêm nhân vật
            </button>
          </div>

          {/* Trigger Generate Button */}
          <div className="flex items-center gap-3 pt-2">
            <button
              className={`flex flex-1 select-none items-center justify-center gap-2.5 rounded-xl px-6 py-3 font-bold text-sm shadow-md transition-all active:scale-95 ${
                isGenerating
                  ? "animate-pulse bg-amber-500 text-white"
                  : "studio-primary"
              } ${script.trim() ? "" : "cursor-not-allowed opacity-50"}`}
              disabled={isGenerating || !script.trim()}
              onClick={handleGenerate}
              type="button"
            >
              <Play className="h-4 w-4 fill-white" />
              <span>
                {isGenerating
                  ? "Đang xử lý ghép nối các đoạn..."
                  : "Tạo Audio Hội thoại / Podcast"}
              </span>
            </button>
          </div>

          {/* Error message */}
          {errorMessage && (
            <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-rose-600 text-xs dark:text-rose-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Speaker Mapping & Podcast Parameters (5 cols) */}
      <div className="studio-span-5 flex flex-col space-y-4">
        {/* Step 2: Speaker Voice Assign Box */}
        <div className="studio-tab-card space-y-4 rounded-[14px] border border-border bg-card p-5 shadow-sm">
          <div className="studio-section-heading flex items-center justify-between border-border/60 border-b pb-3">
            <div className="flex items-center gap-2">
              <Sliders className="h-4 w-4 text-brand-500" />
              <h3 className="font-bold text-foreground text-sm">
                Phân bổ Giọng đọc Nhân vật
              </h3>
            </div>
            <span className="text-muted-foreground text-xs">
              {detectedSpeakers.length} nhân vật
            </span>
          </div>

          {detectedSpeakers.some((spk) => replacedVoices[spk]) && (
            <div
              className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-700 text-xs dark:text-amber-400"
              role="status"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div className="space-y-1">
                {detectedSpeakers
                  .filter((spk) => replacedVoices[spk])
                  .map((spk) => (
                    <p key={spk}>{replacedVoices[spk]}</p>
                  ))}
                <p className="font-medium">Kiểm tra lại trước khi tạo.</p>
              </div>
            </div>
          )}

          {/* Detected Speakers List */}
          <div className="max-h-[220px] space-y-2.5 overflow-y-auto pr-1">
            {detectedSpeakers.length === 0 ? (
              <div className="rounded-xl border border-border border-dashed bg-secondary/30 p-4 text-center text-muted-foreground text-xs">
                Chưa nhận diện được nhân vật. Hãy viết kịch bản dạng{" "}
                <code>[Tên]: Lời thoại</code>.
              </div>
            ) : (
              detectedSpeakers.map((spk, idx) => {
                const color = SPEAKER_COLORS[idx % SPEAKER_COLORS.length];
                const mapped = speakerMapping[spk];
                const currentVoiceId =
                  mapped && voices.some((v) => v.id === mapped)
                    ? mapped
                    : voices[0]?.id || "";

                return (
                  <div
                    className="studio-section-heading flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-secondary/30 p-3"
                    key={spk}
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <div
                        className={`h-7 w-7 rounded-lg bg-gradient-to-tr ${color} flex flex-shrink-0 items-center justify-center font-bold text-white text-xs shadow-sm`}
                      >
                        {spk.slice(0, 1).toUpperCase()}
                      </div>
                      <span className="truncate font-semibold text-foreground text-xs">
                        {spk}
                      </span>
                    </div>

                    {/* Voice Select */}
                    <select
                      className="max-w-[260px] rounded-lg border border-border/80 bg-background px-2.5 py-1.5 text-xs outline-none focus:border-brand-500"
                      onChange={(e) => {
                        setSpeakerMapping((prev) => ({
                          ...prev,
                          [spk]: e.target.value,
                        }));
                        setReplacedVoices((prev) => {
                          const { [spk]: _, ...rest } = prev;
                          return rest;
                        });
                      }}
                      value={currentVoiceId}
                    >
                      {groupVoices(voices).map((g) => (
                        <optgroup key={g.label} label={g.label}>
                          {g.voices.map((v) => (
                            <option key={v.id} value={v.id}>
                              {voiceOptionLabel(v)}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                );
              })
            )}
          </div>

          {/* Podcast Parameters */}
          <div className="space-y-3 border-border/60 border-t pt-3">
            <LanguageSelect />
            {/* Silence interval between dialogue turns */}
            <div>
              <div className="mb-1 flex justify-between font-medium text-foreground text-xs">
                <span>Khoảng nghỉ giữa các câu (Pause):</span>
                <span className="font-bold font-mono text-brand-600 dark:text-brand-400">
                  {silenceDuration.toFixed(2)}s
                </span>
              </div>
              <input
                className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
                max="1.5"
                min="0.1"
                onChange={(e) =>
                  setSilenceDuration(Number.parseFloat(e.target.value))
                }
                step="0.05"
                type="range"
                value={silenceDuration}
              />
              <div className="mt-0.5 flex justify-between text-[12px] text-muted-foreground">
                <span>0.1s (Nhanh)</span>
                <span>0.4s (Tự nhiên)</span>
                <span>1.5s (Chậm)</span>
              </div>
            </div>

            {/* Speed */}
            <div className="pt-1">
              <div>
                <div className="mb-1 flex justify-between text-[12px] text-muted-foreground">
                  <span>Tốc độ:</span>
                  <span className="font-bold font-mono text-foreground">
                    {speed.toFixed(2)}x
                  </span>
                </div>
                <input
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
                  max="1.5"
                  min="0.75"
                  onChange={(e) => setSpeed(Number.parseFloat(e.target.value))}
                  step="0.05"
                  type="range"
                  value={speed}
                />
              </div>
            </div>

            <AdvancedGeneration
              disabled={isGenerating}
              onChangeTemperature={setTemperature}
              temperature={temperature}
            />
          </div>
        </div>

        {/* Output Result Box */}
        {outputUrl && (
          <div className="slide-in-from-bottom-3 animate-in space-y-3 rounded-2xl border border-brand-500/40 bg-card p-5 shadow-sm">
            <div className="studio-section-heading flex items-center justify-between border-border/60 border-b pb-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-brand-500" />
                <h4 className="font-bold text-foreground text-xs">
                  Podcast hoàn tất
                </h4>
              </div>
              <span className="font-mono text-[12px] text-muted-foreground">
                {turnsCount} lượt thoại · Xong trong {elapsedSec?.toFixed(1)}s ·{" "}
                {genDuration?.toFixed(1)}s audio
              </span>
            </div>

            {/* Audio Player */}
            <audio
              className="h-10 w-full"
              controls
              ref={audioRef}
              src={outputUrl}
            />

            {/* Export Buttons */}
            <div className="flex items-center gap-2 pt-1">
              <button
                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-secondary px-3 py-2 font-medium text-foreground text-xs shadow-sm transition-colors hover:bg-secondary/80"
                onClick={handleDownloadWav}
                type="button"
              >
                <Download className="h-3.5 w-3.5 text-brand-500" />
                <span>Tải WAV</span>
              </button>
              <button
                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-secondary px-3 py-2 font-medium text-foreground text-xs shadow-sm transition-colors hover:bg-secondary/80"
                onClick={handleDownloadMp3}
                type="button"
              >
                <Download className="h-3.5 w-3.5 text-cyan-500" />
                <span>Tải MP3</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
