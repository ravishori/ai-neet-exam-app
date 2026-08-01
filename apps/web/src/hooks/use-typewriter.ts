import { useEffect, useRef, useState } from "react";

const TOTAL_DURATION_MS = 900;
const STEP_MS = 16;

/** Reveals `text` progressively (word-chunked, not char-by-char, so markdown
 * tokens like `**bold**` rarely get split mid-render). Skips the animation
 * entirely under prefers-reduced-motion. */
export function useTypewriter(text: string) {
  const [displayedText, setDisplayedText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const reducedMotionRef = useRef(false);

  useEffect(() => {
    reducedMotionRef.current =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (!text) {
      setDisplayedText("");
      setIsTyping(false);
      return;
    }
    if (reducedMotionRef.current) {
      setDisplayedText(text);
      setIsTyping(false);
      return;
    }

    const words = text.split(/(\s+)/);
    const totalSteps = Math.max(1, Math.min(words.length, Math.round(TOTAL_DURATION_MS / STEP_MS)));
    const wordsPerStep = Math.max(1, Math.ceil(words.length / totalSteps));

    let index = 0;
    setDisplayedText("");
    setIsTyping(true);

    const id = setInterval(() => {
      index += wordsPerStep;
      setDisplayedText(words.slice(0, index).join(""));
      if (index >= words.length) {
        clearInterval(id);
        setIsTyping(false);
      }
    }, STEP_MS);

    return () => clearInterval(id);
  }, [text]);

  return { displayedText, isTyping };
}
