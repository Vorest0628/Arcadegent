import { useCallback, useRef, useState } from "react";
import { getAssistantTokenDelta, getAssistantTokenFullText } from "../lib/chatStream";

export function useStreamReply() {
  const [streamReplyTarget, setStreamReplyTarget] = useState("");
  const [streamReplyDisplay, setStreamReplyDisplay] = useState("");

  const streamReplyTargetRef = useRef("");
  const streamReplyDisplayRef = useRef("");
  const streamReplyQueueRef = useRef<string[]>([]);
  const streamReplyFlushTimerRef = useRef<number | null>(null);

  const cancelStreamReplyFlush = useCallback(() => {
    if (streamReplyFlushTimerRef.current !== null) {
      window.clearTimeout(streamReplyFlushTimerRef.current);
      streamReplyFlushTimerRef.current = null;
    }
  }, []);

  const writeStreamReplyTarget = useCallback((value: string) => {
    streamReplyTargetRef.current = value;
    setStreamReplyTarget(value);
  }, []);

  const writeStreamReplyDisplay = useCallback((value: string) => {
    streamReplyDisplayRef.current = value;
    setStreamReplyDisplay(value);
  }, []);

  const flushStreamReplyQueue = useCallback(() => {
    cancelStreamReplyFlush();
    const nextDelta = streamReplyQueueRef.current.shift();

    if (nextDelta) {
      writeStreamReplyDisplay(streamReplyDisplayRef.current + nextDelta);
    } else if (streamReplyDisplayRef.current !== streamReplyTargetRef.current) {
      writeStreamReplyDisplay(streamReplyTargetRef.current);
    }

    if (streamReplyQueueRef.current.length > 0) {
      streamReplyFlushTimerRef.current = window.setTimeout(flushStreamReplyQueue, 28);
    }
  }, [cancelStreamReplyFlush, writeStreamReplyDisplay]);

  const enqueueStreamReplyDelta = useCallback((delta: string) => {
    if (!delta) {
      return;
    }
    streamReplyQueueRef.current.push(delta);
    if (streamReplyFlushTimerRef.current === null) {
      streamReplyFlushTimerRef.current = window.setTimeout(flushStreamReplyQueue, 28);
    }
  }, [flushStreamReplyQueue]);

  const resetStreamReply = useCallback(() => {
    cancelStreamReplyFlush();
    streamReplyQueueRef.current = [];
    writeStreamReplyTarget("");
    writeStreamReplyDisplay("");
  }, [cancelStreamReplyFlush, writeStreamReplyDisplay, writeStreamReplyTarget]);

  const applyStreamToken = useCallback((data: Record<string, unknown>) => {
    const previousTarget = streamReplyTargetRef.current;
    const fullText = getAssistantTokenFullText(data);
    const explicitDelta = getAssistantTokenDelta(data);

    if (fullText && fullText.length >= previousTarget.length) {
      writeStreamReplyTarget(fullText);
      const derivedDelta = fullText.startsWith(previousTarget)
        ? fullText.slice(previousTarget.length)
        : fullText;
      enqueueStreamReplyDelta(derivedDelta);
      return;
    }

    if (explicitDelta) {
      const nextTarget = previousTarget + explicitDelta;
      writeStreamReplyTarget(nextTarget);
      enqueueStreamReplyDelta(explicitDelta);
    }
  }, [enqueueStreamReplyDelta, writeStreamReplyTarget]);

  const syncStreamReply = useCallback((value: string) => {
    cancelStreamReplyFlush();
    streamReplyQueueRef.current = [];
    writeStreamReplyTarget(value);
    writeStreamReplyDisplay(value);
  }, [cancelStreamReplyFlush, writeStreamReplyDisplay, writeStreamReplyTarget]);

  const getStreamReplyTarget = useCallback(() => streamReplyTargetRef.current, []);

  return {
    applyStreamToken,
    cancelStreamReplyFlush,
    getStreamReplyTarget,
    resetStreamReply,
    streamReplyDisplay,
    streamReplyTarget,
    syncStreamReply,
    writeStreamReplyTarget
  };
}
