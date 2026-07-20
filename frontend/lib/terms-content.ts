export interface TermsSection {
  id: string;
  title: string;
  paragraphs?: string[];
  bullets?: string[];
  closingParagraphs?: string[];
}

export const TERMS_EFFECTIVE_DATE = "July 15, 2026";
export const TERMS_VERSION = "MVP Release Version 1.0";

export const TERMS_SECTIONS: TermsSection[] = [
  {
    id: "introduction",
    title: "1. Introduction",
    paragraphs: [
      "Welcome to Speeky, an AI-assisted English language practice platform designed to support users in improving their English communication skills through speech recognition, pronunciation analysis, fluency evaluation, grammar correction, and AI-powered conversational practice.",
      "These Terms and Conditions (\u201CTerms\u201D) govern your access to and use of the Speeky software application, including its associated features, models, documentation, and services (\u201CSoftware\u201D).",
      "By installing, accessing, or using Speeky, you acknowledge that you have read, understood, and agreed to these Terms. If you do not agree with any part of these Terms, you must discontinue use of the Software.",
    ],
  },
  {
    id: "description",
    title: "2. Description of Speeky",
    paragraphs: ["Speeky is an AI-assisted English language learning system that provides:"],
    bullets: [
      "Speech recognition using automatic speech recognition technology.",
      "Speech segmentation using voice activity detection.",
      "Pronunciation analysis through phoneme-level evaluation.",
      "Fluency assessment including speech rate, pauses, filled pauses, and lexical diversity.",
      "Grammar correction using natural language processing models.",
      "AI-powered conversational practice through simulated scenarios.",
      "Text-to-speech functionality using supported voice models.",
      "Local/offline processing capabilities where supported.",
    ],
    closingParagraphs: [
      "Speeky is designed as an educational tool to assist users in practicing and improving their English communication skills.",
    ],
  },
  {
    id: "acceptance",
    title: "3. Acceptance of Terms",
    paragraphs: ["By using Speeky, you confirm that:"],
    bullets: [
      "You agree to comply with these Terms.",
      "You will use the Software responsibly and lawfully.",
      "You understand that AI-generated feedback may not always be completely accurate.",
      "You accept that Speeky is intended for learning purposes only.",
    ],
  },
  {
    id: "eligibility",
    title: "4. Eligibility",
    paragraphs: [
      "You must meet the minimum legal requirements applicable in your jurisdiction to use Speeky.",
      "Users under the required age should only use Speeky with appropriate parental or guardian permission.",
    ],
  },
  {
    id: "license",
    title: "5. License Grant",
    paragraphs: [
      "Subject to compliance with these Terms, Speeky grants you a limited, non-exclusive, non-transferable, and revocable license to use the Software for personal, educational, or authorized organizational purposes.",
      "This license does not grant you ownership rights to the Software or its underlying technologies.",
    ],
  },
  {
    id: "acceptable-use",
    title: "6. Acceptable Use",
    paragraphs: ["Users may use Speeky for:"],
    bullets: [
      "English language learning.",
      "Communication improvement.",
      "Interview preparation.",
      "Workplace communication practice.",
      "Educational activities.",
    ],
    closingParagraphs: ["Users agree not to:"],
  },
  {
    id: "acceptable-use-restrictions",
    title: "",
    bullets: [
      "Use Speeky for illegal activities.",
      "Attempt to gain unauthorized access to the Software.",
      "Reverse engineer, modify, or redistribute proprietary components.",
      "Use Speeky to create harmful or misleading content.",
      "Abuse, exploit, or intentionally disrupt the Software.",
    ],
  },
  {
    id: "ai-disclaimer",
    title: "7. AI-Generated Results Disclaimer",
    paragraphs: [
      "Speeky uses Artificial Intelligence and Machine Learning technologies to provide language feedback.",
      "AI-generated results may include:",
    ],
    bullets: [
      "Speech transcription errors.",
      "Incorrect pronunciation assessments.",
      "Inaccurate grammar suggestions.",
      "Unexpected conversational responses.",
      "Incorrect interpretation of user input.",
    ],
    closingParagraphs: [
      "Speeky's feedback should be considered educational guidance and should not be treated as an official assessment of English proficiency.",
      "Speeky does not replace:",
    ],
  },
  {
    id: "ai-disclaimer-replace",
    title: "",
    bullets: [
      "Certified language examinations.",
      "Professional language instructors.",
      "Speech therapists.",
      "Employment evaluation systems.",
    ],
  },
  {
    id: "pronunciation-assessment",
    title: "8. Pronunciation and Fluency Assessment",
    paragraphs: [
      "Pronunciation scores and fluency measurements generated by Speeky are estimates based on AI analysis.",
      "Results may be affected by:",
    ],
    bullets: [
      "Microphone quality.",
      "Background noise.",
      "Speaking speed.",
      "Accent variations.",
      "Recording conditions.",
      "AI model limitations.",
    ],
    closingParagraphs: [
      "Speeky does not guarantee that generated scores represent a user's actual language ability with complete accuracy.",
    ],
  },
  {
    id: "data-privacy",
    title: "9. Data Privacy and Security",
    paragraphs: [
      "Speeky is designed with privacy-focused processing.",
      "Depending on configuration:",
    ],
    bullets: [
      "Speech processing may occur locally on the user's device.",
      "Audio recordings may remain stored locally.",
      "Transcriptions may be processed locally.",
      "User data is not automatically transmitted to external servers unless explicitly configured.",
    ],
    closingParagraphs: [
      "Users are responsible for maintaining appropriate security measures on their own devices.",
      "Speeky does not guarantee protection against unauthorized access resulting from user negligence, device compromise, or external security incidents.",
    ],
  },
  {
    id: "offline-processing",
    title: "10. Offline Processing and External Services",
    paragraphs: [
      "Speeky supports offline operation through locally deployed AI models.",
      "Some optional features may require additional resources or services, including locally hosted AI systems such as language models.",
      "The availability and performance of these components may depend on:",
    ],
    bullets: [
      "Hardware capabilities.",
      "System configuration.",
      "Installed models.",
      "Third-party software compatibility.",
    ],
  },
  {
    id: "third-party",
    title: "11. Third-Party Technologies",
    paragraphs: [
      "Speeky utilizes third-party open-source technologies and frameworks, which may include:",
    ],
    bullets: [
      "FasterWhisper",
      "SileroVAD",
      "Montreal Forced Aligner (MFA)",
      "Gramformer",
      "spaCy",
      "Ollama",
      "Piper TTS",
    ],
    closingParagraphs: [
      "These components are provided under their respective licenses.",
      "Where applicable, the terms and conditions of third-party licenses shall apply.",
    ],
  },
  {
    id: "ip",
    title: "12. Intellectual Property Rights",
    paragraphs: ["All rights, title, and interest in Speeky, including:"],
    bullets: [
      "Software architecture.",
      "Branding.",
      "Documentation.",
      "User interface design.",
      "Original code.",
      "Custom workflows.",
    ],
    closingParagraphs: [
      "remain the property of the Speeky development team unless otherwise stated.",
      "Nothing in these Terms transfers ownership of Speeky or its components to the user.",
    ],
  },
  {
    id: "availability",
    title: "13. Software Availability",
    paragraphs: [
      "Speeky is provided on an \u201CAS IS\u201D and \u201CAS AVAILABLE\u201D basis.",
      "The developers do not guarantee that:",
    ],
    bullets: [
      "The Software will always operate without errors.",
      "All features will function on every device.",
      "The Software will always be available.",
      "Results generated by AI models will always be accurate.",
    ],
  },
  {
    id: "liability",
    title: "14. Limitation of Liability",
    paragraphs: [
      "To the maximum extent permitted by applicable law, the Speeky development team shall not be responsible for:",
    ],
    bullets: [
      "Loss of data.",
      "Device damage.",
      "Business interruption.",
      "Academic outcomes.",
      "Employment decisions.",
      "Reliance on AI-generated feedback.",
      "Any indirect or consequential damages.",
    ],
    closingParagraphs: [
      "Users assume responsibility for decisions made based on information generated by Speeky.",
    ],
  },
  {
    id: "updates",
    title: "15. Updates and Modifications",
    paragraphs: ["The developers may update Speeky to improve:"],
    bullets: [
      "Performance.",
      "Security.",
      "AI model accuracy.",
      "User experience.",
      "Available features.",
    ],
    closingParagraphs: [
      "Updates may modify or remove certain features without prior notice.",
    ],
  },
  {
    id: "termination",
    title: "16. Termination",
    paragraphs: ["Access to Speeky may be restricted or terminated if a user:"],
    bullets: [
      "Violates these Terms.",
      "Misuses the Software.",
      "Attempts unauthorized modification.",
      "Uses Speeky for unlawful purposes.",
    ],
    closingParagraphs: ["Upon termination, users must stop using the Software."],
  },
  {
    id: "changes",
    title: "17. Changes to These Terms",
    paragraphs: [
      "These Terms may be updated periodically.",
      "Continued use of Speeky after changes are published indicates acceptance of the updated Terms.",
    ],
  },
  {
    id: "governing-law",
    title: "18. Governing Law",
    paragraphs: [
      "These Terms shall be governed by applicable laws of the jurisdiction where Speeky is developed or distributed, unless otherwise required by applicable regulations.",
    ],
  },
  {
    id: "contact",
    title: "19. Contact Information",
    paragraphs: [
      "For questions, feedback, security concerns, or licensing inquiries regarding Speeky, users may contact the Speeky development team through the official project communication channels.",
    ],
  },
  {
    id: "acknowledgement",
    title: "20. Acknowledgement",
    paragraphs: ["By using Speeky, you acknowledge that:"],
    bullets: [
      "You have read and understood these Terms.",
      "Speeky is an AI-assisted educational tool.",
      "AI-generated results may contain limitations.",
      "You agree to use the Software responsibly.",
    ],
  },
];
