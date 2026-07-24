"use client";

import * as React from "react";

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: SpeechRecognitionAlternative;
}

interface SpeechRecognitionEventLike extends Event {
  results: SpeechRecognitionResultLike[];
  resultIndex: number;
}

interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type RecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export function useSpeechRecognition() {
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = React.useRef<(text: string) => void>(() => {});
  const [isListening, setIsListening] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const isSupported = React.useMemo(() => {
    if (typeof window === "undefined") return false;
    const browserWindow = window as RecognitionWindow;
    return Boolean(browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition);
  }, []);

  const stop = React.useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = React.useCallback(
    (onTranscript: (text: string) => void) => {
      if (!isSupported || isListening) return false;

      const browserWindow = window as RecognitionWindow;
      const SpeechRecognitionClass = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
      if (!SpeechRecognitionClass) return false;

      const recognition = new SpeechRecognitionClass();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;

      transcriptRef.current = onTranscript;
      recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
        setError(event.error === "not-allowed" ? "Microphone permission denied." : "Speech recognition failed.");
        setIsListening(false);
      };
      recognition.onend = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };
      recognition.onresult = (event: SpeechRecognitionEventLike) => {
        const result = event.results?.[event.resultIndex];
        const text = result?.[0]?.transcript?.trim() ?? "";
        if (text && result?.isFinal) {
          transcriptRef.current(text);
        }
      };

      setError(null);
      recognitionRef.current = recognition;
      setIsListening(true);
      recognition.start();
      return true;
    },
    [isListening, isSupported]
  );

  React.useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
    };
  }, []);

  return { isSupported, isListening, error, start, stop };
}