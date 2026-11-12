/** Doc file TXT/SRT: UTF-8, hong thi thu Windows-1258 (file Word/Notepad cu cua Viet Nam). */
export async function readTextFile(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1258").decode(bytes);
  }
}
