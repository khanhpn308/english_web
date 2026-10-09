import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';

const compatible = (voice: SpeechSynthesisVoice) =>
  voice.localService === true && voice.lang.toLowerCase() === 'en-us';
// SpeechSynthesis has one queue for the page. Keep only one form playing.
let interruptPlayback: (() => void) | null = null;

export function AudioButton({ text, active = true }: { text: string; active?: boolean }) {
  const descriptionId = useId();
  const [available, setAvailable] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [message, setMessage] = useState('Đang kiểm tra giọng phát âm cục bộ.');
  const synthesis = useRef<SpeechSynthesis | null>(null);
  const current = useRef<SpeechSynthesisUtterance | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const interrupt = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    const utterance = current.current;
    current.current = null;
    if (interruptPlayback === interrupt.current) interruptPlayback = null;
    interrupt.current = null;
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    if (utterance) {
      utterance.onend = null; utterance.onerror = null;
      synthesis.current?.cancel();
    }
  }, []);

  useEffect(() => {
    const engine = window.speechSynthesis;
    if (!engine || typeof window.SpeechSynthesisUtterance !== 'function') {
      setAvailable(false); setMessage('Trình duyệt không hỗ trợ phát âm cục bộ.');
      return;
    }
    synthesis.current = engine;
    const refresh = () => {
      let found = false;
      try { found = engine.getVoices().some(compatible); }
      catch { found = false; }
      setAvailable(found);
      if (!found) { stop(); setPlaying(false); }
      setMessage(found ? 'Giọng Mỹ en-US chạy cục bộ. Không cần quyền AI.' :
        'Không có giọng en-US được xác nhận chạy cục bộ. Phát âm bị tắt.');
    };
    refresh();
    engine.addEventListener('voiceschanged', refresh);
    return () => {
      engine.removeEventListener('voiceschanged', refresh);
      stop(); synthesis.current = null;
    };
  }, [stop]);

  useEffect(() => {
    stop(); setPlaying(false);
    return stop;
  }, [active, text, stop]);

  const play = () => {
    const engine = synthesis.current;
    if (!active || !text.trim() || !engine) return;
    if (current.current) {
      stop(); setPlaying(false); setMessage('Đã dừng phát âm cục bộ.'); return;
    }
    try {
      // Recheck immediately before speaking; never let the browser choose a fallback.
      const voice = engine.getVoices().find(compatible);
      if (!voice) {
        setAvailable(false);
        setMessage('Không có giọng en-US được xác nhận chạy cục bộ. Phát âm bị tắt.');
        return;
      }
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice; utterance.lang = 'en-US';
      interruptPlayback?.();
      engine.cancel();
      current.current = utterance;
      interrupt.current = () => {
        stop(); setPlaying(false); setMessage('Đã dừng phát âm cục bộ.');
      };
      interruptPlayback = interrupt.current;
      const finish = (failed: boolean) => {
        if (current.current !== utterance) return;
        stop(); setPlaying(false);
        setMessage(failed ? 'Không phát âm được bằng giọng cục bộ. Bạn có thể thử lại.' : 'Đã kết thúc phát âm cục bộ.');
      };
      utterance.onend = () => finish(false);
      utterance.onerror = () => finish(true);
      setPlaying(true); setMessage(`Đang phát âm ${text} bằng giọng Mỹ cục bộ.`);
      timer.current = setTimeout(() => finish(true), 15_000);
      engine.speak(utterance);
    } catch {
      stop(); setPlaying(false);
      setMessage('Không phát âm được bằng giọng cục bộ. Bạn có thể thử lại.');
    }
  };

  return <div className="min-w-0 space-y-2 [overflow-wrap:anywhere]">
    <Button type="button" variant="outline" className="min-h-11 max-w-full whitespace-normal"
      disabled={!active || !available || !text.trim()} aria-describedby={descriptionId}
      aria-label={`${playing ? 'Dừng phát âm' : 'Phát âm Mỹ'} ${text}`} onClick={play}>
      {playing ? 'Dừng phát âm' : 'Phát âm Mỹ'} <span lang="en-US">{text}</span>
    </Button>
    <p id={descriptionId} role="status" aria-live="polite" aria-atomic="true" className="text-sm text-muted-foreground">
      {!text.trim() ? 'Chưa có dạng từ để phát âm.' : !active ? 'Phát âm đã dừng khi rời trang tra cứu.' : message}
    </p>
  </div>;
}
