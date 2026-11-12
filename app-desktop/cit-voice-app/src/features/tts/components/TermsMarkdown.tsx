import type React from "react";

// Hiển thị DIEU-KHOAN.md cho dễ đọc mà không kéo thêm thư viện markdown: chỉ hỗ trợ
// đúng những gì file điều khoản dùng - tiêu đề #/##, đoạn văn (dòng xuống hàng giữa
// đoạn được nối lại), danh sách "-" và "1.", **đậm**, `code` và đường link http(s).

interface ListBlock {
  items: string[];
  kind: "ul" | "ol";
}
interface TextBlock {
  kind: "h1" | "h2" | "p";
  text: string;
}
type Block = ListBlock | TextBlock;

const CRLF = /\r\n/g;
const HEADING = /^(#{1,2})\s+/;
const BULLET = /^-\s+/;
const NUMBERED = /^\d+\.\s+/;
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s)]+)/g;
const TRAILING_PUNCT = /[.,;:]+$/;

const isList = (b: Block | undefined): b is ListBlock =>
  b?.kind === "ul" || b?.kind === "ol";

function listKind(line: string): ListBlock["kind"] | null {
  if (BULLET.test(line)) {
    return "ul";
  }
  return NUMBERED.test(line) ? "ol" : null;
}

// Thêm một dòng vào danh sách khối. Trả về true nếu khối cuối còn nhận dòng tiếp
// theo (false sau dòng trống hoặc tiêu đề).
function addLine(blocks: Block[], raw: string, open: boolean): boolean {
  const line = raw.trim();
  if (!line) {
    return false;
  }
  const heading = HEADING.exec(line);
  if (heading) {
    blocks.push({
      kind: heading[1].length === 1 ? "h1" : "h2",
      text: line.slice(heading[0].length),
    });
    return false;
  }
  const last = open ? blocks[blocks.length - 1] : undefined;
  const kind = listKind(line);
  if (kind) {
    const item = line.replace(kind === "ul" ? BULLET : NUMBERED, "");
    if (isList(last) && last.kind === kind) {
      last.items.push(item);
    } else {
      blocks.push({ kind, items: [item] });
    }
    return true;
  }
  // Dòng thụt vào là phần tiếp của mục danh sách đang dở.
  if (isList(last) && raw.startsWith(" ")) {
    last.items[last.items.length - 1] += ` ${line}`;
    return true;
  }
  if (last?.kind === "p") {
    last.text += ` ${line}`;
  } else {
    blocks.push({ kind: "p", text: line });
  }
  return true;
}

function parse(markdown: string): Block[] {
  const blocks: Block[] = [];
  let open = false;
  for (const raw of markdown.replace(CRLF, "\n").split("\n")) {
    open = addLine(blocks, raw, open);
  }
  return blocks;
}

function inline(text: string): React.ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    const key = `${i}:${part}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code className="rounded bg-secondary px-1 text-[12px]" key={key}>
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("http")) {
      const url = part.replace(TRAILING_PUNCT, "");
      return (
        <span key={key}>
          <a
            className="text-sky-600 underline dark:text-sky-400"
            href={url}
            rel="noreferrer"
            target="_blank"
          >
            {url}
          </a>
          {part.slice(url.length)}
        </span>
      );
    }
    return part;
  });
}

function renderBlock(b: Block, key: string): React.ReactNode {
  if (isList(b)) {
    const items = b.items.map((it) => <li key={it}>{inline(it)}</li>);
    return b.kind === "ul" ? (
      <ul className="list-disc space-y-1 pl-5" key={key}>
        {items}
      </ul>
    ) : (
      <ol className="list-decimal space-y-1 pl-5" key={key}>
        {items}
      </ol>
    );
  }
  if (b.kind === "h1") {
    return (
      <h3 className="font-bold text-lg" key={key}>
        {inline(b.text)}
      </h3>
    );
  }
  if (b.kind === "h2") {
    return (
      <h4 className="pt-2 font-bold text-[15px]" key={key}>
        {inline(b.text)}
      </h4>
    );
  }
  return <p key={key}>{inline(b.text)}</p>;
}

export const TermsMarkdown: React.FC<{ text: string }> = ({ text }) => (
  <div className="space-y-3 text-[13.5px] text-foreground leading-relaxed">
    {parse(text).map((b, i) => renderBlock(b, `${b.kind}-${i}`))}
  </div>
);
