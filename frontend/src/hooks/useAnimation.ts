import { useEffect, useRef, useState } from "react";

/** Eases a number toward its target; used by the resilience gauge. */
export function useCountUp(value: number, duration = 650): number {
  const [display, setDisplay] = useState(value);
  const current = useRef(value);

  useEffect(() => {
    const from = current.current;
    const startedAt = Date.now();
    let timer = 0;

    const step = () => {
      const progress = Math.min(1, Math.max(0, (Date.now() - startedAt) / duration));
      const eased = 1 - (1 - progress) ** 3;
      const next = from + (value - from) * eased;
      current.current = next;
      setDisplay(next);
      if (progress >= 1) window.clearInterval(timer);
    };

    timer = window.setInterval(step, 16);
    return () => window.clearInterval(timer);
  }, [value, duration]);

  return display;
}

/** Types out a block of text one character at a time. */
export function useTypewriter(
  text: string,
  speed = 9,
): { output: string; typing: boolean } {
  const [count, setCount] = useState(0);

  useEffect(() => {
    setCount(0);
    if (!text) return;

    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      setCount(index);
      if (index >= text.length) window.clearInterval(timer);
    }, speed);

    return () => window.clearInterval(timer);
  }, [text, speed]);

  return { output: text.slice(0, count), typing: count < text.length };
}
