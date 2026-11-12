import { TtsStudio } from "@/features/tts/TtsStudio";

export function HomePage() {
  return <TtsStudio />;
}

// Necessary for react router to lazy load.
export const Component = HomePage;
